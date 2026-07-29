from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from afac2026.api import call_image, extract_markdown, import_cached_response  # noqa: E402
from afac2026.batch_plan import build_batch_plan  # noqa: E402
from afac2026.batch_run import run_batch  # noqa: E402
from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.image_plan import (  # noqa: E402
    image_info,
    layout_family,
    vertical_crop_plan,
    whole_image_limit,
)
from afac2026.local_table_ocr import ocr_dense_tables  # noqa: E402
from afac2026.normalize import conservative_normalize  # noqa: E402
from afac2026.score import diagnose  # noqa: E402
from afac2026.table_grid import analyze_table_layout  # noqa: E402
from afac2026.table_repair import repair_table_warnings  # noqa: E402
from afac2026.table_tiles import all_tile_specs, render_tile  # noqa: E402


def command_inspect(settings: Settings, output: Path | None) -> int:
    layout = DatasetLayout.discover(settings.data_root)
    records = [image_info(path).to_dict() for path in (*layout.train_images, *layout.test_images)]
    report = {
        "train_images": len(layout.train_images),
        "train_markdowns": len(layout.train_markdowns),
        "test_images": len(layout.test_images),
        "submission_template": str(layout.submission_template),
        "images": records,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(output),
                    "train_images": len(layout.train_images),
                    "train_markdowns": len(layout.train_markdowns),
                    "test_images": len(layout.test_images),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(text)
    return 0


def command_plan(settings: Settings, image: Path) -> int:
    info = image_info(image)
    family = layout_family(info)
    limit = whole_image_limit(info, settings.whole_image_max_pixels)
    whole_allowed = info.pixels <= limit
    crops = []
    if family != "dense_table" and not whole_allowed:
        crops = vertical_crop_plan(info, settings.crop_max_pixels, settings.crop_overlap_pixels)
    result = {
        "image": info.to_dict(),
        "layout_family": family,
        "whole_image_allowed": whole_allowed,
        "strategy": (
            "whole_image"
            if whole_allowed
            else "grid_tiling_required"
            if family == "dense_table"
            else "vertical_overlap_crops"
        ),
        "warning": (
            "高密表格需要行组×列组二维切片；禁止直接纵向滑窗"
            if family == "dense_table" and not whole_allowed
            else None
        ),
        "crops": [crop.__dict__ for crop in crops],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_probe(settings: Settings, image: Path, gt: Path | None, force: bool) -> int:
    result = call_image(image, settings, force=force)
    report: dict[str, object] = {
        "image": str(image),
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "cache_hit": result.cache_hit,
        "cache_key": result.cache_key,
        "markdown_chars": len(result.markdown),
    }
    if gt:
        report["diagnostic"] = diagnose(
            result.markdown,
            gt.read_text(encoding="utf-8"),
        ).to_dict()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def command_evaluate(prediction: Path, gt: Path) -> int:
    score = diagnose(
        conservative_normalize(prediction.read_text(encoding="utf-8")),
        gt.read_text(encoding="utf-8"),
    )
    print(json.dumps(score.to_dict(), ensure_ascii=False, indent=2))
    return 0


def command_import_response(raw_response: Path, output: Path) -> int:
    markdown = extract_markdown(raw_response.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    print(json.dumps({"output": str(output), "chars": len(markdown)}, ensure_ascii=False))
    return 0


def command_import_cache(
    settings: Settings,
    image: Path,
    raw_response: Path,
    elapsed_seconds: float,
) -> int:
    result = import_cached_response(image, raw_response, settings, elapsed_seconds)
    print(
        json.dumps(
            {
                "cache_key": result.cache_key,
                "markdown_chars": len(result.markdown),
                "cache_dir": str(settings.cache_dir / "api" / result.cache_key),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_table_plan(image: Path, output: Path | None) -> int:
    layout = analyze_table_layout(image)
    text = json.dumps(layout.to_dict(), ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(output),
                    "region_count": len(layout.regions),
                    "tile_count_estimate": layout.tile_count_estimate,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(text)
    return 0


def command_render_table_tile(
    image: Path,
    region_index: int,
    row_group_index: int,
    column_group_index: int,
    output: Path,
) -> int:
    layout = analyze_table_layout(image)
    matches = [
        spec
        for spec in all_tile_specs(layout)
        if spec.region_index == region_index
        and spec.row_group_index == row_group_index
        and spec.column_group_index == column_group_index
    ]
    if len(matches) != 1:
        raise ValueError("请求的表格切片索引不存在或不唯一")
    result = render_tile(image, layout, matches[0], output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_local_table_ocr(
    settings: Settings,
    image: Path,
    output: Path,
    model_root: Path,
    cpu_threads: int,
) -> int:
    report = ocr_dense_tables(
        image_path=image,
        output_path=output,
        cache_dir=settings.cache_dir,
        model_root=model_root,
        cpu_threads=cpu_threads,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


def command_batch_plan(settings: Settings, output: Path) -> int:
    plan = build_batch_plan(settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(output)
    print(json.dumps({"output": str(output), **plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


def command_batch_run(
    settings: Settings,
    plan: Path,
    phase: str,
    model_root: Path,
    api_workers: int,
    local_workers: int,
    local_cpu_threads: int,
    submission: Path | None,
    file_names: tuple[str, ...],
) -> int:
    report = run_batch(
        settings=settings,
        plan_path=plan,
        phase=phase,  # type: ignore[arg-type]
        model_root=model_root,
        api_workers=api_workers,
        local_workers=local_workers,
        local_cpu_threads=local_cpu_threads,
        submission_path=submission,
        file_names=file_names,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


def command_repair_table_warnings(
    settings: Settings,
    plan: Path,
    model_root: Path,
    workers: int,
    cpu_threads: int,
    min_grid_cells: int,
    file_names: tuple[str, ...],
) -> int:
    report = repair_table_warnings(
        settings=settings,
        plan_path=plan,
        model_root=model_root,
        workers=workers,
        cpu_threads=cpu_threads,
        min_grid_cells=min_grid_cells,
        file_names=file_names,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] or report["unresolved"] else 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="AFAC2026 FinixDoc-VL workflow")
    sub = root.add_subparsers(dest="command", required=True)
    inspect_p = sub.add_parser("inspect", help="校验数据并输出图像规格")
    inspect_p.add_argument("--output", type=Path)
    plan_p = sub.add_parser("plan", help="仅生成切块计划，不解码或上传图片")
    plan_p.add_argument("image", type=Path)
    probe_p = sub.add_parser("probe", help="调用一张图片，结果自动缓存")
    probe_p.add_argument("image", type=Path)
    probe_p.add_argument("--gt", type=Path)
    probe_p.add_argument("--force", action="store_true", help="忽略缓存并重新调用")
    eval_p = sub.add_parser("evaluate", help="本地文本/表格/块顺序诊断")
    eval_p.add_argument("prediction", type=Path)
    eval_p.add_argument("gt", type=Path)
    import_p = sub.add_parser("import-response", help="导入已缓存的原始API响应")
    import_p.add_argument("raw_response", type=Path)
    import_p.add_argument("output", type=Path)
    cache_p = sub.add_parser("import-cache", help="把已有原始响应导入内容寻址缓存")
    cache_p.add_argument("image", type=Path)
    cache_p.add_argument("raw_response", type=Path)
    cache_p.add_argument("--elapsed-seconds", type=float, default=0.0)
    table_p = sub.add_parser("table-plan", help="离线检测高密表格区域和二维切片规模")
    table_p.add_argument("image", type=Path)
    table_p.add_argument("--output", type=Path)
    render_p = sub.add_parser("render-table-tile", help="离线渲染一个二维表格切片")
    render_p.add_argument("image", type=Path)
    render_p.add_argument("--region", type=int, required=True)
    render_p.add_argument("--row-group", type=int, required=True)
    render_p.add_argument("--column-group", type=int, required=True)
    render_p.add_argument("--output", type=Path, required=True)
    local_p = sub.add_parser(
        "local-table-ocr",
        help="使用合规的 PP-OCRv6 tiny CPU 模型离线重建高密表格",
    )
    local_p.add_argument("image", type=Path)
    local_p.add_argument("--output", type=Path, required=True)
    local_p.add_argument(
        "--model-root",
        type=Path,
        default=Path("D:/AFAC2026/models/paddlex/official_models"),
    )
    local_p.add_argument("--cpu-threads", type=int, default=8)
    batch_p = sub.add_parser(
        "batch-plan",
        help="为 A 榜生成只读路由与调用量计划，不运行 OCR 或 API",
    )
    batch_p.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_batch_plan.json"),
    )
    run_p = sub.add_parser(
        "batch-run",
        help="按计划断点续跑 A 榜预测，并在全部完成后生成提交 CSV",
    )
    run_p.add_argument(
        "--plan", type=Path, default=Path("D:/AFAC2026/outputs/a_batch_plan.json")
    )
    run_p.add_argument(
        "--phase", choices=("api", "local", "submission", "all"), default="all"
    )
    run_p.add_argument(
        "--model-root",
        type=Path,
        default=Path("D:/AFAC2026/models/paddlex/official_models"),
    )
    run_p.add_argument("--api-workers", type=int, default=2)
    run_p.add_argument("--local-workers", type=int, default=2)
    run_p.add_argument("--local-cpu-threads", type=int, default=6)
    run_p.add_argument("--submission", type=Path)
    run_p.add_argument(
        "--file-name",
        action="append",
        default=[],
        help="只运行指定图片，可重复；用于小规模验证，不生成提交文件",
    )
    repair_p = sub.add_parser(
        "repair-table-warnings",
        help="用自适应网格 tiny OCR 修复被 API 截断的表格预测",
    )
    repair_p.add_argument(
        "--plan", type=Path, default=Path("D:/AFAC2026/outputs/a_batch_plan.json")
    )
    repair_p.add_argument(
        "--model-root",
        type=Path,
        default=Path("D:/AFAC2026/models/paddlex/official_models"),
    )
    repair_p.add_argument("--workers", type=int, default=3)
    repair_p.add_argument("--cpu-threads", type=int, default=4)
    repair_p.add_argument("--min-grid-cells", type=int, default=500)
    repair_p.add_argument("--file-name", action="append", default=[])
    return root


def main() -> int:
    args = parser().parse_args()
    settings = Settings.load(PROJECT_ROOT)
    if args.command == "inspect":
        return command_inspect(settings, args.output)
    if args.command == "plan":
        return command_plan(settings, args.image)
    if args.command == "probe":
        return command_probe(settings, args.image, args.gt, args.force)
    if args.command == "evaluate":
        return command_evaluate(args.prediction, args.gt)
    if args.command == "import-response":
        return command_import_response(args.raw_response, args.output)
    if args.command == "import-cache":
        return command_import_cache(settings, args.image, args.raw_response, args.elapsed_seconds)
    if args.command == "table-plan":
        return command_table_plan(args.image, args.output)
    if args.command == "render-table-tile":
        return command_render_table_tile(
            args.image,
            args.region,
            args.row_group,
            args.column_group,
            args.output,
        )
    if args.command == "local-table-ocr":
        return command_local_table_ocr(
            settings,
            args.image,
            args.output,
            args.model_root,
            args.cpu_threads,
        )
    if args.command == "batch-plan":
        return command_batch_plan(settings, args.output)
    if args.command == "batch-run":
        return command_batch_run(
            settings,
            args.plan,
            args.phase,
            args.model_root,
            args.api_workers,
            args.local_workers,
            args.local_cpu_threads,
            args.submission,
            tuple(args.file_name),
        )
    if args.command == "repair-table-warnings":
        return command_repair_table_warnings(
            settings,
            args.plan,
            args.model_root,
            args.workers,
            args.cpu_threads,
            args.min_grid_cells,
            tuple(args.file_name),
        )
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
