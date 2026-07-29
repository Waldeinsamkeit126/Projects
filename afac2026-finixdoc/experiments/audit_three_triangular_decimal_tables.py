from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.score import _TableParser  # noqa: E402


TERMINAL = 108


def parse_one(path: Path) -> _TableParser:
    parsed = _TableParser()
    parsed.feed(path.read_text(encoding="utf-8"))
    if parsed.tables != 1:
        raise ValueError(f"{path} contains {parsed.tables} tables, expected one")
    return parsed


def expected_headers(columns: int) -> list[list[str]]:
    return [
        ["", "投保年龄", *([""] * (columns - 2))],
        ["保单年度末", *[str(value) for value in range(columns - 1)]],
    ]


def report_table(
    parsed: _TableParser,
    *,
    rows: int,
    columns: int,
    first_key: int,
    last_key: int,
    headers: bool,
) -> dict[str, object]:
    values = parsed.cell_text_rows
    expected_header_rows = expected_headers(columns) if headers else []
    data = values[len(expected_header_rows) :]
    expected_keys = [str(value) for value in range(first_key, last_key + 1)]
    actual_keys = [row[0].strip() for row in data]
    key_mismatches = [
        {"row": index, "expected": expected, "actual": actual}
        for index, (expected, actual) in enumerate(zip(expected_keys, actual_keys))
        if expected != actual
    ]
    row_lengths = list(map(len, parsed.rows))
    whitespace_repairs: list[dict[str, object]] = []
    numeric_anomalies: list[dict[str, object]] = []
    duplicate_cells: list[dict[str, object]] = []
    prefix_mismatches: list[dict[str, object]] = []
    for row_index, row in enumerate(data):
        key = first_key + row_index
        expected_nonempty = min(columns, TERMINAL - key)
        internal_blanks = [
            column
            for column, cell in enumerate(row[:expected_nonempty])
            if not cell.strip()
        ]
        trailing_values = [
            [column, cell]
            for column, cell in enumerate(row[expected_nonempty:], expected_nonempty)
            if cell.strip()
        ]
        if internal_blanks or trailing_values:
            prefix_mismatches.append(
                {
                    "row": row_index,
                    "key": key,
                    "expected_nonempty": expected_nonempty,
                    "internal_blanks": internal_blanks,
                    "trailing_values": trailing_values,
                }
            )
        for column_index, cell in enumerate(row[1:], 1):
            value = cell.strip()
            if not value:
                continue
            compact = re.sub(r"\s+", "", value)
            if re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
                pass
            elif re.fullmatch(r"[0-9]+\.[0-9]{2}", compact):
                whitespace_repairs.append(
                    {
                        "row": row_index,
                        "column": column_index,
                        "old": value,
                        "new": compact,
                    }
                )
            else:
                numeric_anomalies.append(
                    {
                        "row": row_index,
                        "column": column_index,
                        "text": value,
                    }
                )
            tokens = value.split()
            if len(tokens) > 1 and len(set(tokens)) == 1:
                duplicate_cells.append(
                    {"row": row_index, "column": column_index, "text": value}
                )
    header_exact = not headers or values[:2] == expected_header_rows
    plain_cells = all(
        row == [("td", None, None)] * columns for row in parsed.rows
    )
    expected_nonempty_total = sum(
        min(columns, TERMINAL - key)
        for key in range(first_key, last_key + 1)
    ) + sum(bool(cell) for row in expected_header_rows for cell in row)
    actual_nonempty_total = sum(
        bool(cell.strip()) for row in values for cell in row
    )
    structure_ok = (
        len(parsed.rows) == rows
        and row_lengths == [columns] * rows
        and plain_cells
        and header_exact
        and actual_keys == expected_keys
        and actual_nonempty_total == expected_nonempty_total
        and not numeric_anomalies
        and not duplicate_cells
        and not prefix_mismatches
    )
    return {
        "rows": len(parsed.rows),
        "columns": sorted(set(row_lengths)),
        "plain_cells": plain_cells,
        "header_exact": header_exact,
        "keys_exact": actual_keys == expected_keys,
        "key_mismatches": key_mismatches,
        "first_keys": actual_keys[:4],
        "last_keys": actual_keys[-4:],
        "expected_nonempty_cells": expected_nonempty_total,
        "actual_nonempty_cells": actual_nonempty_total,
        "whitespace_repairs": whitespace_repairs,
        "numeric_anomalies": numeric_anomalies,
        "duplicate_cells": duplicate_cells,
        "prefix_mismatches": prefix_mismatches,
        "structure_ok": structure_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table1", type=Path, required=True)
    parser.add_argument("--table2", type=Path, required=True)
    parser.add_argument("--table3", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [
        report_table(
            parse_one(args.table1),
            rows=33,
            columns=72,
            first_key=74,
            last_key=106,
            headers=False,
        ),
        report_table(
            parse_one(args.table2),
            rows=108,
            columns=72,
            first_key=1,
            last_key=106,
            headers=True,
        ),
        report_table(
            parse_one(args.table3),
            rows=44,
            columns=67,
            first_key=1,
            last_key=42,
            headers=True,
        ),
    ]
    result = {
        "tables": reports,
        "expected_nonempty_cells": sum(
            int(report["expected_nonempty_cells"]) for report in reports
        ),
        "actual_nonempty_cells": sum(
            int(report["actual_nonempty_cells"]) for report in reports
        ),
        "whitespace_repairs": sum(
            len(report["whitespace_repairs"]) for report in reports
        ),
        "structure_ok": all(bool(report["structure_ok"]) for report in reports),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
