from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.constrained_table_ocr import constrained_table_ocr  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import diagnose  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_name")
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--gt-name")
    parser.add_argument("--merged-title-row", action="store_true")
    parser.add_argument("--corner-header-span", action="store_true")
    parser.add_argument("--corner-header-columns", type=int)
    parser.add_argument("--rule-grid", action="store_true")
    parser.add_argument("--header-vertical-rules", action="store_true")
    parser.add_argument("--rule-grid-max-width", type=int, default=3000)
    parser.add_argument(
        "--rule-grid-horizontal-coverage", type=float, default=0.35
    )
    parser.add_argument(
        "--rule-grid-header-vertical-coverage", type=float, default=0.50
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("D:/AFAC2026/models/paddlex/official_models"),
    )
    parser.add_argument("--cpu-threads", type=int, default=4)
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    images = {path.name: path for path in [*data.train_images, *data.test_images]}
    markdowns = {path.name: path for path in data.train_markdowns}
    image_path = images[args.image_name]
    markdown, report = constrained_table_ocr(
        image_path,
        args.rows,
        args.columns,
        settings.cache_dir,
        args.model_root,
        args.cpu_threads,
        (
            [1, *([args.columns] * (args.rows - 1))]
            if args.merged_title_row
            else None
        ),
        args.corner_header_span,
        args.corner_header_columns,
        args.rule_grid,
        args.header_vertical_rules,
        args.rule_grid_max_width,
        args.rule_grid_horizontal_coverage,
        args.rule_grid_header_vertical_coverage,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(markdown + "\n", encoding="utf-8")
    temporary.replace(args.output)
    result: dict[str, object] = {
        "image": str(image_path),
        "output": str(args.output),
        **report,
    }
    if args.gt_name:
        ground_truth = markdowns[args.gt_name].read_text(encoding="utf-8")
        result["diagnostic"] = diagnose(markdown, ground_truth).to_dict()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
