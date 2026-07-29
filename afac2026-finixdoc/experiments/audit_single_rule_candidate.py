from __future__ import annotations

import argparse
import csv
import difflib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        return {
            str(row["file_name"]): str(row["ground_truth"])
            for row in csv.DictReader(stream)
        }


def parse(markdown: str) -> tuple[_TableParser, list[str]]:
    parsed = _TableParser()
    parsed.feed(markdown)
    cells = [
        normalized_for_alignment(cell)
        for row in parsed.cell_text_rows
        for cell in row
        if normalized_for_alignment(cell)
    ]
    return parsed, cells


def summary(markdown: str) -> dict[str, object]:
    parsed, cells = parse(markdown)
    lengths = list(map(len, parsed.rows))
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "row_lengths": sorted(set(lengths)),
        "first_row_lengths": lengths[:3],
        "nonempty_cells": len(cells),
        "normalized_cell_characters": sum(map(len, cells)),
        "header_rows": parsed.cell_text_rows[:2],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_name")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--header-columns", type=int, required=True)
    parser.add_argument(
        "--submission",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v11.csv"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("work_single_rule_candidate.json")
    )
    args = parser.parse_args()
    candidate = args.candidate.read_text(encoding="utf-8")
    current = load_submission(args.submission)[args.image_name]
    parsed, candidate_cells = parse(candidate)
    _, current_cells = parse(current)
    if args.header_columns == 0:
        expected_lengths = [args.columns] * args.rows
        expected_first = [("td", None, None)] * args.columns
    else:
        expected_lengths = [
            args.header_columns + 1,
            args.columns - args.header_columns,
            *([args.columns] * (args.rows - 2)),
        ]
        expected_first = [
            *([("td", "2", None)] * args.header_columns),
            ("td", None, str(args.columns - args.header_columns)),
        ]
    matcher = difflib.SequenceMatcher(
        None, candidate_cells, current_cells, autojunk=False
    )
    exact = sum(block.size for block in matcher.get_matching_blocks())
    report = {
        "file_name": args.image_name,
        "candidate": str(args.candidate),
        "submission": str(args.submission),
        "structure_ok": (
            parsed.tables == 1
            and list(map(len, parsed.rows)) == expected_lengths
            and parsed.rows[0] == expected_first
        ),
        "candidate_summary": summary(candidate),
        "current_summary": summary(current),
        "agreement": {
            "ordered_exact_cells": exact,
            "candidate_coverage": exact / max(1, len(candidate_cells)),
            "current_coverage": exact / max(1, len(current_cells)),
            "sequence_ratio": matcher.ratio(),
        },
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
