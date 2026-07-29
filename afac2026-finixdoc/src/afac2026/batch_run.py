from __future__ import annotations

import json
import hashlib
import math
import os
import time
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Literal

from PIL import Image

from .api import call_image
from .config import Settings
from .data import DatasetLayout
from .local_table_ocr import ocr_dense_tables
from .merge import merge_many
from .submission import write_submission


Phase = Literal["api", "local", "submission", "all"]
ROUTES = ("finixA1001", "finixB2002", "finixC3003", "finixD4004", "finixE5005")


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _render_vertical_crops(
    image_path: Path,
    crop_records: list[dict[str, int]],
    cache_dir: Path,
) -> list[Path]:
    destinations = [
        cache_dir
        / "input_crops"
        / image_path.stem
        / f"v{crop['index']:03d}_y{crop['top']}_{crop['bottom']}.jpg"
        for crop in crop_records
    ]
    missing = [index for index, path in enumerate(destinations) if not path.is_file()]
    if not missing:
        return destinations
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as source:
            for index in missing:
                crop = crop_records[index]
                destination = destinations[index]
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(".jpg.tmp")
                piece = source.crop(
                    (crop["left"], crop["top"], crop["right"], crop["bottom"])
                ).convert("RGB")
                piece.save(
                    temporary,
                    format="JPEG",
                    quality=95,
                    subsampling=0,
                    optimize=True,
                )
                os.replace(temporary, destination)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    return destinations


def _render_downscaled(
    image_path: Path,
    max_pixels: int,
    cache_dir: Path,
) -> Path:
    destination = cache_dir / "input_crops" / image_path.stem / f"downscaled_{max_pixels}.jpg"
    if destination.is_file():
        return destination
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as source:
            width, height = source.size
            scale = min(1.0, math.sqrt(max_pixels / max(width * height, 1)))
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            resized = source.convert("RGB")
            if resized.size != target:
                resized = resized.resize(target, Image.Resampling.LANCZOS)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".jpg.tmp")
            resized.save(
                temporary,
                format="JPEG",
                quality=95,
                subsampling=0,
                optimize=True,
            )
            os.replace(temporary, destination)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    return destination


def _prediction_warnings(markdown: str, expect_table: bool = False) -> list[str]:
    lower = markdown.lower()
    warnings: list[str] = []
    if len(markdown.strip()) < 50:
        warnings.append("very_short_output")
    if 10_500 <= len(markdown) <= 12_000:
        warnings.append("near_api_output_cap")
    if lower.count("<table") != lower.count("</table>"):
        warnings.append("unclosed_table")
    if expect_table and "<table" not in lower:
        warnings.append("table_markup_missing")
    if markdown.count("�") >= 2:
        warnings.append("replacement_characters")
    return warnings


def _routing_signature(record: dict[str, object]) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_warnings(record: dict[str, object], markdown: str) -> list[str]:
    expect_table = (
        record.get("strategy") == "local_tiny_ocr_table"
        or "table" in str(record.get("path", "")).lower()
    )
    return _prediction_warnings(markdown, expect_table=expect_table)


def _prediction_meta_path(output_path: Path) -> Path:
    return output_path.with_suffix(".meta.json")


def _completed_prediction(
    output_path: Path,
    record: dict[str, object],
) -> dict[str, object] | None:
    meta_path = _prediction_meta_path(output_path)
    if not output_path.is_file() or not output_path.stat().st_size or not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("strategy") != record.get("strategy"):
        return None
    if meta.get("routing_signature") != _routing_signature(record):
        return None
    return meta


def _write_prediction_meta(
    output_path: Path,
    record: dict[str, object],
    producer: str,
    markdown: str,
) -> None:
    warnings = _record_warnings(record, markdown)
    if producer != "finixdoc_api":
        warnings = [item for item in warnings if item != "near_api_output_cap"]
    _atomic_text(
        _prediction_meta_path(output_path),
        json.dumps(
            {
                "file_name": record["file_name"],
                "strategy": record["strategy"],
                "producer": producer,
                "routing_signature": _routing_signature(record),
                "chars": len(markdown),
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def _run_api_record(
    base_settings: Settings,
    record: dict[str, object],
    output_path: Path,
    route_index: int,
) -> dict[str, object]:
    strategy = str(record["strategy"])
    if _completed_prediction(output_path, record) is not None:
        markdown = output_path.read_text(encoding="utf-8")
        return {
            "file_name": record["file_name"],
            "kind": "api",
            "skipped": True,
            "chars": len(markdown),
            "warnings": _record_warnings(record, markdown),
        }
    settings = replace(base_settings, user_id=ROUTES[route_index % 2])
    image_path = Path(str(record["path"]))
    if strategy == "api_vertical_overlap":
        raw_crops = record.get("crops")
        if not isinstance(raw_crops, list):
            raise ValueError(f"missing crop plan: {image_path}")
        crop_records = [dict(item) for item in raw_crops]
        crop_paths = _render_vertical_crops(image_path, crop_records, settings.cache_dir)
        results = [call_image(path, settings) for path in crop_paths]
        markdown = merge_many([result.markdown for result in results])
    elif strategy == "api_downscaled_grid_fallback":
        max_pixels = int(record.get("downscale_max_pixels") or settings.crop_max_pixels)
        resized = _render_downscaled(image_path, max_pixels, settings.cache_dir)
        results = [call_image(resized, settings)]
        markdown = results[0].markdown
    else:
        results = [call_image(image_path, settings)]
        markdown = results[0].markdown
    _atomic_text(output_path, markdown + "\n")
    _write_prediction_meta(output_path, record, "finixdoc_api", markdown)
    return {
        "file_name": record["file_name"],
        "kind": "api",
        "skipped": False,
        "calls": len(results),
        "cache_hits": sum(result.cache_hit for result in results),
        "chars": len(markdown),
        "warnings": _record_warnings(record, markdown),
    }


def _run_local_record(
    settings: Settings,
    record: dict[str, object],
    output_path: Path,
    model_root: Path,
    cpu_threads: int,
) -> dict[str, object]:
    strategy = str(record["strategy"])
    if _completed_prediction(output_path, record) is not None:
        return {
            "file_name": record["file_name"],
            "kind": "local",
            "skipped": True,
            "chars": len(output_path.read_text(encoding="utf-8")),
        }
    report = ocr_dense_tables(
        image_path=Path(str(record["path"])),
        output_path=output_path,
        cache_dir=settings.cache_dir,
        model_root=model_root,
        cpu_threads=cpu_threads,
        content_relative_rules=record.get("table_rule_scope") == "content",
    )
    markdown = output_path.read_text(encoding="utf-8")
    _write_prediction_meta(output_path, record, "ppocrv6_tiny_cpu", markdown)
    return {"file_name": record["file_name"], "kind": "local", **report.to_dict()}


def _load_plan(path: Path) -> list[dict[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("plan_version") != 3:
        raise ValueError("批量计划版本过旧；请先重新运行 main.py batch-plan")
    images = value.get("images")
    if not isinstance(images, list) or len(images) != 100:
        raise ValueError("批量计划必须恰好包含 100 张 A 榜图片")
    return [dict(record) for record in images]


def _write_status(path: Path, status: dict[str, object]) -> None:
    _atomic_text(path, json.dumps(status, ensure_ascii=False, indent=2) + "\n")


def run_batch(
    settings: Settings,
    plan_path: Path,
    phase: Phase,
    model_root: Path,
    api_workers: int = 2,
    local_workers: int = 2,
    local_cpu_threads: int = 6,
    submission_path: Path | None = None,
    file_names: tuple[str, ...] = (),
) -> dict[str, object]:
    records = _load_plan(plan_path)
    if file_names:
        selected = set(file_names)
        known = {str(record["file_name"]) for record in records}
        if not selected <= known:
            raise ValueError(f"计划中不存在这些文件: {sorted(selected - known)}")
        records = [record for record in records if record["file_name"] in selected]
    prediction_dir = settings.output_dir / "predictions_A"
    status_path = settings.output_dir / "a_batch_status.json"
    started = time.perf_counter()
    completed: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    futures: dict[Future[dict[str, object]], str] = {}

    api_records = [record for record in records if str(record["strategy"]).startswith("api_")]
    local_records = [record for record in records if record["strategy"] == "local_tiny_ocr_table"]
    run_api = phase in {"api", "all"}
    run_local = phase in {"local", "all"}

    with ThreadPoolExecutor(max_workers=api_workers) as api_pool, ProcessPoolExecutor(
        max_workers=local_workers
    ) as local_pool:
        if run_api:
            for index, record in enumerate(api_records):
                name = str(record["file_name"])
                future = api_pool.submit(
                    _run_api_record,
                    settings,
                    record,
                    prediction_dir / f"{Path(name).stem}.md",
                    index,
                )
                futures[future] = name
        if run_local:
            for record in local_records:
                name = str(record["file_name"])
                future = local_pool.submit(
                    _run_local_record,
                    settings,
                    record,
                    prediction_dir / f"{Path(name).stem}.md",
                    model_root,
                    local_cpu_threads,
                )
                futures[future] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                completed.append(result)
                print(
                    json.dumps(
                        {
                            "progress": f"{len(completed) + len(errors)}/{len(futures)}",
                            **result,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except Exception as exc:  # The status file preserves every failure for reruns.
                error = {"file_name": name, "error": f"{type(exc).__name__}: {exc}"}
                errors.append(error)
                print(json.dumps(error, ensure_ascii=False), flush=True)
            _write_status(
                status_path,
                {
                    "phase": phase,
                    "completed": completed,
                    "errors": errors,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                },
            )

    submission: str | None = None
    if phase in {"submission", "all"} and not errors and not file_names:
        dataset = DatasetLayout.discover(settings.data_root)
        record_by_name = {str(record["file_name"]): record for record in records}
        predictions: dict[str, str] = {}
        warning_items: list[dict[str, object]] = []
        for image in dataset.test_images:
            path = prediction_dir / f"{image.stem}.md"
            record = record_by_name[image.name]
            meta = _completed_prediction(path, record)
            if meta is None:
                raise FileNotFoundError(f"缺少与当前路由匹配的预测或元数据: {path}")
            if meta.get("warnings"):
                warning_items.append(
                    {"file_name": image.name, "warnings": meta["warnings"]}
                )
            predictions[image.name] = path.read_text(encoding="utf-8")
        if warning_items:
            raise RuntimeError(
                "存在未解决的预测质量警告，拒绝生成提交: "
                + json.dumps(warning_items, ensure_ascii=False)
            )
        destination = submission_path or settings.output_dir / "afac_A_submission.csv"
        write_submission(dataset.submission_template, predictions, destination)
        submission = str(destination)

    report = {
        "phase": phase,
        "planned": len(futures),
        "completed": len(completed),
        "errors": errors,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "submission": submission,
        "filtered_files": list(file_names),
        "status": str(status_path),
    }
    _write_status(status_path, {**report, "items": completed})
    return report
