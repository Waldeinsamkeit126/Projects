from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402


def load_prediction(path: Path, image_name: str) -> str:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        matches = [
            str(row["ground_truth"])
            for row in csv.DictReader(stream)
            if str(row["file_name"]) == image_name
        ]
    if len(matches) != 1:
        raise ValueError(f"expected one submission row, found {len(matches)}")
    return matches[0]


def parse_tables(markdown: str) -> list[_TableParser]:
    matches = re.findall(r"<table[^>]*>.*?</table>", markdown, flags=re.I | re.S)
    parsed: list[_TableParser] = []
    for match in matches:
        table = _TableParser()
        table.feed(match)
        if table.tables != 1:
            raise ValueError("isolated table did not parse exactly once")
        parsed.append(table)
    return parsed


def nonempty_cells(markdown: str) -> list[str]:
    parsed = _TableParser()
    parsed.feed(markdown)
    return [
        normalized_for_alignment(cell)
        for row in parsed.cell_text_rows
        for cell in row
        if normalized_for_alignment(cell)
    ]


def table_report(
    parsed: _TableParser,
    rows: int,
    columns: int,
    keys: list[str],
    header: list[str] | None = None,
) -> dict[str, object]:
    row_lengths = list(map(len, parsed.rows))
    values = parsed.cell_text_rows
    data = values[1:] if header is not None else values
    actual_keys = [row[0].strip() for row in data]
    numeric_anomalies: list[dict[str, object]] = []
    prefix_mismatches: list[dict[str, object]] = []
    duplicate_cells: list[dict[str, object]] = []
    for row_index, row in enumerate(data):
        key = int(keys[row_index]) if row_index < len(keys) else 0
        expected_nonempty = min(columns, 107 - key)
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
            if cell.strip() and not re.fullmatch(r"[0-9]+", cell):
                numeric_anomalies.append(
                    {"row": row_index, "column": column_index, "text": cell}
                )
            tokens = cell.split()
            if len(tokens) > 1 and len(set(tokens)) == 1:
                duplicate_cells.append(
                    {"row": row_index, "column": column_index, "text": cell}
                )
    plain_cells = all(
        row == [("td", None, None)] * columns for row in parsed.rows
    )
    report = {
        "rows": len(parsed.rows),
        "columns": sorted(set(row_lengths)),
        "nonempty_cells": sum(bool(cell.strip()) for row in values for cell in row),
        "plain_cells": plain_cells,
        "header_exact": header is None or values[0] == header,
        "keys_exact": actual_keys == keys,
        "first_keys": actual_keys[:4],
        "last_keys": actual_keys[-4:],
        "numeric_anomalies": numeric_anomalies,
        "prefix_mismatches": prefix_mismatches,
        "duplicate_cells": duplicate_cells,
    }
    report["structure_ok"] = (
        len(parsed.rows) == rows
        and row_lengths == [columns] * rows
        and plain_cells
        and bool(report["header_exact"])
        and actual_keys == keys
        and not numeric_anomalies
        and not prefix_mismatches
        and not duplicate_cells
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_name")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = args.candidate.read_text(encoding="utf-8").strip()
    old = load_prediction(args.submission, args.image_name)
    tables = parse_tables(candidate)
    outside = re.sub(
        r"<table[^>]*>.*?</table>", "", candidate, flags=re.I | re.S
    ).strip()
    if len(tables) == 2:
        first = table_report(
            tables[0], 73, 72, [str(value) for value in range(33, 106)]
        )
        second = table_report(
            tables[1],
            74,
            67,
            [str(value) for value in range(1, 74)],
            ["年度/年龄", *[str(value) for value in range(66)]],
        )
    else:
        first = {"structure_ok": False}
        second = {"structure_ok": False}
    candidate_cells = nonempty_cells(candidate)
    old_cells = nonempty_cells(old)
    matcher = difflib.SequenceMatcher(
        None, candidate_cells, old_cells, autojunk=False
    )
    exact = sum(block.size for block in matcher.get_matching_blocks())
    report = {
        "file_name": args.image_name,
        "candidate": str(args.candidate),
        "submission": str(args.submission),
        "tables": len(tables),
        "outside_text": outside,
        "first_table": first,
        "second_table": second,
        "structure_ok": (
            len(tables) == 2
            and not outside
            and bool(first["structure_ok"])
            and bool(second["structure_ok"])
            and len(candidate_cells) == 7_168
        ),
        "agreement": {
            "candidate_nonempty_cells": len(candidate_cells),
            "old_nonempty_cells": len(old_cells),
            "ordered_exact_cells": exact,
            "candidate_coverage": exact / max(1, len(candidate_cells)),
            "old_coverage": exact / max(1, len(old_cells)),
            "sequence_ratio": matcher.ratio(),
        },
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "structure_ok": report["structure_ok"],
                "first_table": first,
                "second_table": second,
                "agreement": report["agreement"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
