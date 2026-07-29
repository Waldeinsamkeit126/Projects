from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.score import _TableParser  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, required=True)
    parser.add_argument("--expected-columns", type=int, required=True)
    parser.add_argument("--skip-leading-rows", type=int, default=0)
    args = parser.parse_args()

    markdown = args.input.read_text(encoding="utf-8")
    parsed = _TableParser()
    parsed.feed(markdown)
    all_rows = parsed.cell_text_rows
    rows = all_rows[args.skip_leading_rows :]
    if parsed.tables != 1:
        raise ValueError(f"expected one table, found {parsed.tables}")
    if len(rows) != args.expected_rows:
        raise ValueError(f"expected {args.expected_rows} rows, found {len(rows)}")
    lengths = [len(row) for row in rows]
    if set(lengths) != {args.expected_columns}:
        raise ValueError(f"unexpected row lengths: {sorted(set(lengths))}")

    age_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    invalid_age_rows: list[int] = []
    for index, row in enumerate(rows):
        try:
            age = int(row[2])
        except ValueError:
            invalid_age_rows.append(index)
            continue
        age_groups[(row[0], row[1], row[3])].append(age)

    groups: list[dict[str, object]] = []
    for key, ages in age_groups.items():
        unique = set(ages)
        expected = set(range(min(ages), max(ages) + 1))
        groups.append(
            {
                "key": list(key),
                "count": len(ages),
                "minimum_age": min(ages),
                "maximum_age": max(ages),
                "missing_ages": sorted(expected - unique),
                "duplicate_ages": sorted(
                    age for age, count in Counter(ages).items() if count > 1
                ),
                "encountered_ages": ages,
            }
        )

    transitions: list[dict[str, object]] = []
    start = 0
    previous = tuple(rows[0][:2])
    for index, row in enumerate(rows[1:], start=1):
        current = tuple(row[:2])
        if current == previous:
            continue
        transitions.append(
            {"key": list(previous), "start": start, "end": index - 1}
        )
        start = index
        previous = current
    transitions.append(
        {"key": list(previous), "start": start, "end": len(rows) - 1}
    )

    duplicate_token_cells: list[dict[str, object]] = []
    comma_numeric_cells: list[dict[str, object]] = []
    nonstandard_numeric_cells: list[dict[str, object]] = []
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            tokens = value.split()
            if len(tokens) > 1 and len(set(tokens)) == 1:
                duplicate_token_cells.append(
                    {"row": row_index, "column": column_index, "value": value}
                )
            if re.fullmatch(r"[0-9]+,[0-9]+", value):
                comma_numeric_cells.append(
                    {"row": row_index, "column": column_index, "value": value}
                )
            if (
                column_index >= 4
                and value.strip()
                and not re.fullmatch(r"[0-9]+\.[0-9]{2}", value)
            ):
                nonstandard_numeric_cells.append(
                    {"row": row_index, "column": column_index, "value": value}
                )

    nonempty_counts = [sum(bool(value.strip()) for value in row) for row in rows]
    triangular_mismatches: list[dict[str, object]] = []
    for row_index, row in enumerate(rows):
        try:
            age = int(row[2])
        except ValueError:
            continue
        expected_nonempty = len(row) - age
        internal_blanks = [
            column
            for column, value in enumerate(row[:expected_nonempty])
            if not value.strip()
        ]
        overflow_nonempty = [
            column
            for column, value in enumerate(row[expected_nonempty:], expected_nonempty)
            if value.strip()
        ]
        if internal_blanks or overflow_nonempty:
            triangular_mismatches.append(
                {
                    "row": row_index,
                    "age": age,
                    "expected_nonempty": expected_nonempty,
                    "internal_blank_columns": internal_blanks,
                    "overflow_nonempty_columns": overflow_nonempty,
                }
            )
    report = {
        "input": str(args.input),
        "tables": parsed.tables,
        "skipped_leading_rows": args.skip_leading_rows,
        "rows": len(rows),
        "columns": sorted(set(lengths)),
        "first_keys": [row[:4] for row in rows[:8]],
        "last_keys": [row[:4] for row in rows[-8:]],
        "key_column_values": [
            Counter(row[column] for row in rows).most_common()
            for column in range(4)
        ],
        "invalid_age_rows": invalid_age_rows,
        "age_groups": groups,
        "first_two_column_runs": transitions,
        "nonempty_cells": sum(nonempty_counts),
        "nonempty_columns_per_row": {
            "minimum": min(nonempty_counts),
            "maximum": max(nonempty_counts),
            "frequencies": Counter(nonempty_counts).most_common(),
        },
        "triangular_mismatches": triangular_mismatches,
        "duplicate_token_cells": duplicate_token_cells,
        "comma_numeric_cells": comma_numeric_cells,
        "nonstandard_numeric_cells": nonstandard_numeric_cells,
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
