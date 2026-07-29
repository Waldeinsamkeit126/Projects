from __future__ import annotations

import json
import shutil
import time
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path

from .batch_run import (
    _atomic_text,
    _load_plan,
    _prediction_meta_path,
    _write_prediction_meta,
)
from .config import Settings
from .local_table_ocr import (
    local_layout_stats,
    ocr_dense_tables,
    prefer_content_relative_layout,
)
from .table_grid import analyze_table_layout


def _atomic_status(path: Path, value: dict[str, object]) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _warning_meta(output_path: Path) -> dict[str, object] | None:
    meta_path = _prediction_meta_path(output_path)
    if not output_path.is_file() or not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return meta if meta.get("warnings") else None


def _choose_layout_scope(
    image_path: Path,
    min_grid_cells: int,
) -> tuple[str, dict[str, int | bool]]:
    page = analyze_table_layout(image_path, content_relative_rules=False)
    page_stats = local_layout_stats(page, min_grid_cells=min_grid_cells)
    if page_stats["suitable"]:
        return "page", page_stats

    content = analyze_table_layout(image_path, content_relative_rules=True)
    content_stats = local_layout_stats(content, min_grid_cells=min_grid_cells)
    page_cells = int(page_stats["total_cells"])
    if content_stats["suitable"] and (
        page_cells == 0
        or prefer_content_relative_layout(page_stats, content_stats)
        or int(content_stats["total_cells"]) > page_cells
    ):
        return "content", content_stats
    raise ValueError(
        "table grid is not suitable for local repair: "
        f"page={page_stats}, content={content_stats}"
    )


def _backup_prediction(output_path: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for source in (output_path, _prediction_meta_path(output_path)):
        if source.is_file():
            destination = backup_dir / source.name
            if not destination.exists():
                shutil.copy2(source, destination)


def _repair_one(
    settings: Settings,
    record: dict[str, object],
    output_path: Path,
    model_root: Path,
    cpu_threads: int,
    min_grid_cells: int,
) -> dict[str, object]:
    image_path = Path(str(record["path"]))
    scope, stats = _choose_layout_scope(image_path, min_grid_cells)
    _backup_prediction(
        output_path,
        settings.output_dir / "repair_backups" / output_path.stem,
    )
    report = ocr_dense_tables(
        image_path=image_path,
        output_path=output_path,
        cache_dir=settings.cache_dir,
        model_root=model_root,
        cpu_threads=cpu_threads,
        content_relative_rules=scope == "content",
        min_grid_cells=min_grid_cells,
    )
    markdown = output_path.read_text(encoding="utf-8")
    _write_prediction_meta(
        output_path,
        record,
        "ppocrv6_tiny_cpu_quality_fallback",
        markdown,
    )
    return {
        "file_name": record["file_name"],
        "scope": scope,
        "chars": len(markdown),
        "layout": stats,
        **report.to_dict(),
    }


def repair_table_warnings(
    settings: Settings,
    plan_path: Path,
    model_root: Path,
    workers: int = 3,
    cpu_threads: int = 4,
    min_grid_cells: int = 500,
    file_names: tuple[str, ...] = (),
) -> dict[str, object]:
    records = _load_plan(plan_path)
    selected = set(file_names)
    if selected:
        known = {str(record["file_name"]) for record in records}
        if not selected <= known:
            raise ValueError(f"unknown file names: {sorted(selected - known)}")
    prediction_dir = settings.output_dir / "predictions_A"
    candidates: list[tuple[dict[str, object], Path]] = []
    for record in records:
        name = str(record["file_name"])
        if selected and name not in selected:
            continue
        if "table" not in str(record.get("path", "")).lower():
            continue
        output_path = prediction_dir / f"{Path(name).stem}.md"
        if _warning_meta(output_path) is not None:
            candidates.append((record, output_path))

    started = time.perf_counter()
    completed: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    status_path = settings.output_dir / "a_repair_status.json"
    futures: dict[Future[dict[str, object]], str] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for record, output_path in candidates:
            future = pool.submit(
                _repair_one,
                settings,
                record,
                output_path,
                model_root,
                cpu_threads,
                min_grid_cells,
            )
            futures[future] = str(record["file_name"])
        for future in as_completed(futures):
            name = futures[future]
            try:
                item = future.result()
                completed.append(item)
                print(
                    json.dumps(
                        {
                            "progress": f"{len(completed) + len(errors)}/{len(futures)}",
                            **item,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except Exception as exc:
                error = {"file_name": name, "error": f"{type(exc).__name__}: {exc}"}
                errors.append(error)
                print(json.dumps(error, ensure_ascii=False), flush=True)
            _atomic_status(
                status_path,
                {
                    "planned": len(futures),
                    "completed": completed,
                    "errors": errors,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                },
            )

    unresolved = []
    for record, output_path in candidates:
        meta = _warning_meta(output_path)
        if meta is not None:
            unresolved.append(
                {"file_name": record["file_name"], "warnings": meta.get("warnings")}
            )
    result = {
        "planned": len(candidates),
        "completed": len(completed),
        "errors": errors,
        "unresolved": unresolved,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "status": str(status_path),
    }
    _atomic_status(status_path, result)
    return result
