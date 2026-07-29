from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import html
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402
from audit_three_triangular_decimal_tables import (  # noqa: E402
    TERMINAL,
    expected_headers,
    parse_one,
    report_table,
)
from audit_two_triangular_integer_tables import (  # noqa: E402
    nonempty_cells,
    parse_tables,
)


TARGET = "471413c1-992f-43c7-9b41-287418fcb319.jpg"
EXPECTED_NONEMPTY = 8_695
TABLE_SPECS = (
    {"rows": 33, "columns": 72, "first_key": 74, "last_key": 106, "headers": False},
    {"rows": 108, "columns": 72, "first_key": 1, "last_key": 106, "headers": True},
    {"rows": 44, "columns": 67, "first_key": 1, "last_key": 42, "headers": True},
)

# Each value was read directly from a 10x enlargement of its original grid cell.
VISUALLY_VERIFIED_OVERRIDES = {
    (0, 10, 19): "31944.57",
    (0, 10, 22): "31930.55",
    (0, 15, 7): "37103.88",
    (1, 20, 51): "7426.72",
    (1, 35, 12): "11753.24",
    (1, 48, 52): "16994.23",
}


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected base columns: {reader.fieldnames}")
        rows = list(reader)
    predictions = {
        str(row["file_name"]): str(row["ground_truth"]) for row in rows
    }
    if len(rows) != 100 or len(predictions) != 100:
        raise ValueError(
            f"base must contain 100 unique samples: rows={len(rows)}, "
            f"unique={len(predictions)}"
        )
    return predictions


def serialize_table(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def clean_table(
    path: Path,
    table_index: int,
    spec: dict[str, object],
) -> tuple[str, list[dict[str, object]]]:
    parsed = parse_one(path)
    rows = [list(map(str.strip, row)) for row in parsed.cell_text_rows]
    expected_rows = int(spec["rows"])
    columns = int(spec["columns"])
    first_key = int(spec["first_key"])
    last_key = int(spec["last_key"])
    has_headers = bool(spec["headers"])
    if len(rows) != expected_rows or any(len(row) != columns for row in rows):
        raise ValueError(f"unexpected raw shape for table {table_index}")
    repairs: list[dict[str, object]] = []
    header_count = 2 if has_headers else 0
    if has_headers:
        expected = expected_headers(columns)
        for row_index in range(2):
            for column_index in range(columns):
                old = rows[row_index][column_index]
                new = expected[row_index][column_index]
                if old != new:
                    repairs.append(
                        {
                            "kind": "header",
                            "table": table_index,
                            "row": row_index,
                            "column": column_index,
                            "old": old,
                            "new": new,
                        }
                    )
                rows[row_index][column_index] = new
    for data_index, key in enumerate(range(first_key, last_key + 1)):
        row_index = data_index + header_count
        row = rows[row_index]
        expected_nonempty = min(columns, TERMINAL - key)
        old_key = row[0]
        if old_key != str(key):
            repairs.append(
                {
                    "kind": "key",
                    "table": table_index,
                    "row": row_index,
                    "column": 0,
                    "old": old_key,
                    "new": str(key),
                }
            )
        row[0] = str(key)
        for column_index in range(1, expected_nonempty):
            old = row[column_index]
            new = re.sub(r"\s+", "", old).replace(",", ".").replace("-", "")
            override = VISUALLY_VERIFIED_OVERRIDES.get(
                (table_index, row_index, column_index)
            )
            if override is not None:
                new = override
            if not re.fullmatch(r"[0-9]+\.[0-9]{2}", new):
                raise ValueError(
                    f"unrepaired numeric cell t{table_index} r{row_index} "
                    f"c{column_index}: {old!r} -> {new!r}"
                )
            if old != new:
                repairs.append(
                    {
                        "kind": "visual_override" if override else "punctuation",
                        "table": table_index,
                        "row": row_index,
                        "column": column_index,
                        "old": old,
                        "new": new,
                    }
                )
            row[column_index] = new
        overflow = [
            [column_index, value]
            for column_index, value in enumerate(
                row[expected_nonempty:], expected_nonempty
            )
            if value
        ]
        if overflow:
            raise ValueError(
                f"unexpected triangular overflow t{table_index} r{row_index}: {overflow}"
            )
    return serialize_table(rows), repairs


def structure_report(markdown: str) -> dict[str, object]:
    tables = parse_tables(markdown)
    reports: list[dict[str, object]] = []
    if len(tables) == len(TABLE_SPECS):
        for parsed, spec in zip(tables, TABLE_SPECS):
            reports.append(report_table(parsed, **spec))
    cells = nonempty_cells(markdown)
    outside = re.sub(
        r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S
    ).strip()
    structure_ok = (
        len(tables) == 3
        and not outside
        and all(bool(report["structure_ok"]) for report in reports)
        and len(cells) == EXPECTED_NONEMPTY
    )
    return {
        "tables": len(tables),
        "outside_text": outside,
        "nonempty_cells": len(cells),
        "table_reports": reports,
        "structure_ok": structure_ok,
    }


def ordered_cell_agreement(candidate: str, old: str) -> dict[str, object]:
    candidate_cells = nonempty_cells(candidate)
    old_cells = nonempty_cells(old)
    matcher = difflib.SequenceMatcher(
        None, candidate_cells, old_cells, autojunk=False
    )
    exact = sum(block.size for block in matcher.get_matching_blocks())
    return {
        "candidate_nonempty_cells": len(candidate_cells),
        "old_nonempty_cells": len(old_cells),
        "ordered_exact_cells": exact,
        "candidate_coverage": exact / max(1, len(candidate_cells)),
        "old_coverage": exact / max(1, len(old_cells)),
        "sequence_ratio": matcher.ratio(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v16.csv"),
    )
    parser.add_argument(
        "--table1",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule33x72_A_471413_table1.md"),
    )
    parser.add_argument(
        "--table2",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule108x72_A_471413_table2.md"),
    )
    parser.add_argument(
        "--table3",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule44x67_A_471413_table3.md"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path("D:/AFAC2026/outputs/experiments/rule_combined_A_471413.md"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v17.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v17.report.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base_predictions = load_submission(args.base)
    old = base_predictions[TARGET]
    cleaned: list[str] = []
    repairs: list[dict[str, object]] = []
    for table_index, (path, spec) in enumerate(
        zip((args.table1, args.table2, args.table3), TABLE_SPECS)
    ):
        markdown, table_repairs = clean_table(path, table_index, spec)
        cleaned.append(markdown)
        repairs.extend(table_repairs)
    candidate = "\n\n".join(cleaned)
    structure = structure_report(candidate)
    if not bool(structure["structure_ok"]):
        raise ValueError(f"candidate structure failed: {structure}")
    agreement = ordered_cell_agreement(candidate, old)
    if int(agreement["candidate_nonempty_cells"]) != EXPECTED_NONEMPTY:
        raise ValueError(f"candidate cell count changed: {agreement}")
    if int(agreement["old_nonempty_cells"]) != 6_697:
        raise ValueError(f"base sample no longer matches audited v16: {agreement}")
    if float(agreement["old_coverage"]) < 0.99:
        raise ValueError(f"candidate did not preserve enough old cells: {agreement}")
    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text(candidate + "\n", encoding="utf-8")
    predictions = dict(base_predictions)
    predictions[TARGET] = candidate
    write_submission(data.submission_template, predictions, args.output)
    written = load_submission(args.output)
    changed_names = sorted(
        name for name, value in written.items() if value != base_predictions[name]
    )
    if changed_names != [TARGET]:
        raise ValueError(f"unexpected written changes: {changed_names}")
    if any(not value.strip() for value in written.values()):
        raise ValueError("written submission contains a blank prediction")
    repair_counts: dict[str, int] = {}
    for repair in repairs:
        kind = str(repair["kind"])
        repair_counts[kind] = repair_counts.get(kind, 0) + 1
    report = {
        "base": str(args.base),
        "output": str(args.output),
        "candidate": str(args.candidate),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "rows": len(predictions),
        "changed_samples": 1,
        "validation": {
            "written_rows": len(written),
            "unique_file_names": len(set(written)),
            "blank_predictions": 0,
            "changed_names": changed_names,
        },
        "change": {
            "file_name": TARGET,
            "old_characters": len(old),
            "new_characters": len(candidate),
            "added_characters": len(candidate) - len(old),
            "structure": structure,
            "agreement": agreement,
            "repair_counts": repair_counts,
            "repairs": repairs,
            "evidence": {
                "shapes": [[33, 72], [108, 72], [44, 67]],
                "two_dimensional_successes": [120, 102, 99],
                "two_dimensional_configurations": [120, 120, 120],
                "ocr_tiles": [4, 8, 4],
                "ocr_detections": [594, 5_220, 2_881],
                "expected_nonempty_formula": "min(columns, 108 - row_key)",
                "visually_verified_overrides": len(VISUALLY_VERIFIED_OVERRIDES),
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": report["sha256"],
                "structure_ok": structure["structure_ok"],
                "agreement": agreement,
                "repair_counts": repair_counts,
                "changed_names": changed_names,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
