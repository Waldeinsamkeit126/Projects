from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.constrained_table_ocr import detect_page_text  # noqa: E402
from afac2026.local_table_ocr import _cell_text  # noqa: E402


LEFT = 282.0
KEY_RIGHT = 395.0
RIGHT = 5640.0
DATA_COLUMNS = 106
TOTAL_COLUMNS = DATA_COLUMNS + 1


@dataclass(frozen=True)
class TableSpec:
    label: str
    first_key: int
    rows: int
    top: float
    bottom: float


PROFILES = {
    "test": (
        TableSpec("male-single", 0, 69, 415.0, 1381.0),
        TableSpec("female-single", 0, 69, 1451.0, 2417.0),
        TableSpec("male-3", 0, 70, 2486.0, 3466.0),
        TableSpec("female-3", 0, 59, 3535.0, 4361.0),
    ),
    "test185": (
        TableSpec("previous-tail", 54, 12, 302.0, 470.0),
        TableSpec("male-20", 0, 56, 540.0, 1324.0),
        TableSpec("female-20", 0, 56, 1393.0, 2177.0),
    ),
    "train": (
        TableSpec("previous-tail", 59, 11, 302.0, 456.0),
        TableSpec("male-5", 0, 70, 526.0, 1506.0),
        TableSpec("female-5", 0, 70, 1575.0, 2555.0),
        TableSpec("male-10", 0, 66, 2624.0, 3548.0),
        TableSpec("female-10", 0, 54, 3618.0, 4374.0),
    ),
}


def table_html(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--cpu-threads", type=int, default=6)
    args = parser.parse_args()

    detections, ocr_report = detect_page_text(
        args.image,
        args.cache_dir,
        args.model_root,
        cpu_threads=args.cpu_threads,
    )
    tables: list[list[list[str]]] = []
    reports: list[dict[str, object]] = []
    for spec in PROFILES[args.profile]:
        row_height = (spec.bottom - spec.top) / spec.rows
        row_detections = [[] for _ in range(spec.rows)]
        for item in detections:
            if not spec.top <= item.center_y < spec.bottom:
                continue
            row_index = int((item.center_y - spec.top) / row_height)
            if not 0 <= row_index < spec.rows or not LEFT <= item.center_x < RIGHT:
                continue
            row_detections[row_index].append(item)
        rows: list[list[str]] = []
        count_mismatches: list[dict[str, object]] = []
        for row_index, raw_row in enumerate(row_detections):
            key = spec.first_key + row_index
            expected = TOTAL_COLUMNS - key
            ordered = sorted(raw_row, key=lambda item: item.center_x)
            if len(ordered) != expected:
                count_mismatches.append(
                    {
                        "key": key,
                        "expected": expected,
                        "detected": len(ordered),
                        "texts": [item.text for item in ordered],
                    }
                )
            row = [
                _cell_text(
                    [(item.top, item.left, item.text, item.score)],
                    row_index,
                    column,
                )
                for column, item in enumerate(ordered[:TOTAL_COLUMNS])
            ]
            row.extend([""] * (TOTAL_COLUMNS - len(row)))
            rows.append(row)
        tables.append(rows)
        reports.append(
            {
                "label": spec.label,
                "first_key": spec.first_key,
                "rows": spec.rows,
                "columns": TOTAL_COLUMNS,
                "top": spec.top,
                "bottom": spec.bottom,
                "row_height": row_height,
                "assigned_detections": sum(map(len, row_detections)),
                "count_mismatches": count_mismatches,
                "nonempty_cells": sum(bool(value.strip()) for row in rows for value in row),
                "row_nonempty": [sum(bool(value.strip()) for value in row) for row in rows],
                "keys": [row[0] for row in rows],
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(table_html(rows) for rows in tables) + "\n", encoding="utf-8")
    result = {
        "image": str(args.image),
        "profile": args.profile,
        "geometry": {
            "left": LEFT,
            "key_right": KEY_RIGHT,
            "right": RIGHT,
            "columns": TOTAL_COLUMNS,
        },
        "ocr": ocr_report,
        "tables": reports,
    }
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
