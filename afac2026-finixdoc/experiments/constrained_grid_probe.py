from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.constrained_table_ocr import constrained_table_ocr  # noqa: E402
from afac2026.score import _TableParser, diagnose  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--gt", type=Path)
    parser.add_argument("--rows", type=int)
    parser.add_argument("--columns", type=int)
    parser.add_argument("--rule-grid", action="store_true")
    parser.add_argument("--rule-grid-max-width", type=int, default=3000)
    parser.add_argument(
        "--rule-grid-horizontal-coverage", type=float, default=0.35
    )
    parser.add_argument("--rule-grid-strict-bounds", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("D:/AFAC2026/models/paddlex/official_models"),
    )
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument(
        "--recognition-model-name", default="PP-OCRv6_tiny_rec"
    )
    parser.add_argument("--recognition-model-dir", type=Path)
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    gt = args.gt.read_text(encoding="utf-8") if args.gt else None
    rows, columns = args.rows, args.columns
    if gt is not None and (rows is None or columns is None):
        parsed = _TableParser()
        parsed.feed(gt)
        if parsed.tables != 1:
            raise ValueError("automatic shape inference requires one GT table")
        rows = len(parsed.cell_text_rows)
        columns = max(map(len, parsed.cell_text_rows))
    if rows is None or columns is None:
        raise ValueError("provide --gt or both --rows and --columns")
    markdown, report = constrained_table_ocr(
        args.image,
        rows,
        columns,
        settings.cache_dir,
        args.model_root,
        args.cpu_threads,
        use_rule_grid=args.rule_grid,
        rule_grid_max_width=args.rule_grid_max_width,
        rule_grid_horizontal_coverage=args.rule_grid_horizontal_coverage,
        rule_grid_strict_bounds=args.rule_grid_strict_bounds,
        recognition_model_name=args.recognition_model_name,
        recognition_model_dir=args.recognition_model_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown + "\n", encoding="utf-8")
    result: dict[str, object] = {"output": str(args.output), **report}
    if gt is not None:
        result["diagnostic"] = diagnose(markdown, gt).to_dict()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
