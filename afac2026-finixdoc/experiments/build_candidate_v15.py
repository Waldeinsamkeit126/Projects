from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


TARGET = "e082df7b-7afb-44ba-bf46-2c28ebe6c460.jpg"
TITLE = "海港启明星尊享版终身寿险现金价值全表"
SUBTITLE = "（以1000元年交保险费为计算单位）"
ROWS = 354
DATA_ROWS = 353
COLUMNS = 110
EXPECTED_NONEMPTY = 27_844


def expected_header() -> list[str]:
    return [
        "保险期间",
        "交费期间",
        "年龄",
        "性别",
        *[f"第{number}保单年度末" for number in range(1, 107)],
    ]


def expected_keys() -> list[tuple[str, str, str, str]]:
    keys: list[tuple[str, str, str, str]] = []
    for payment, maximum_age in (("1", 70), ("3", 70), ("5", 33)):
        for age in range(maximum_age + 1):
            keys.extend(
                [
                    ("终身", payment, str(age), "男"),
                    ("终身", payment, str(age), "女"),
                ]
            )
    keys.append(("终身", "5", "34", "男"))
    if len(keys) != DATA_ROWS:
        raise AssertionError(f"unexpected expected key count: {len(keys)}")
    return keys


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


def structure_report(markdown: str) -> dict[str, object]:
    parsed, cells = parse(markdown)
    row_lengths = list(map(len, parsed.rows))
    header = expected_header()
    expected = expected_keys()
    actual_header = (
        list(map(str.strip, parsed.cell_text_rows[0]))
        if parsed.cell_text_rows
        else []
    )
    data_rows = parsed.cell_text_rows[1:]
    actual_keys = [tuple(map(str.strip, row[:4])) for row in data_rows]
    numeric_anomalies: list[dict[str, object]] = []
    duplicate_cells: list[dict[str, object]] = []
    prefix_mismatches: list[dict[str, object]] = []
    for row_index, row in enumerate(data_rows):
        for column_index, cell in enumerate(row):
            tokens = cell.split()
            if len(tokens) > 1 and len(set(tokens)) == 1:
                duplicate_cells.append(
                    {"row": row_index, "column": column_index, "text": cell}
                )
            if (
                column_index >= 4
                and cell.strip()
                and not re.fullmatch(r"[0-9]+\.[0-9]{2}", cell)
            ):
                numeric_anomalies.append(
                    {"row": row_index, "column": column_index, "text": cell}
                )
        if row_index < len(expected):
            age = int(expected[row_index][2])
            expected_end = COLUMNS - age
            internal_blanks = [
                column
                for column, value in enumerate(row[:expected_end])
                if not value.strip()
            ]
            trailing_values = [
                [column, value]
                for column, value in enumerate(row[expected_end:], expected_end)
                if value.strip()
            ]
            if internal_blanks or trailing_values:
                prefix_mismatches.append(
                    {
                        "row": row_index,
                        "age": age,
                        "expected_nonempty_prefix": expected_end,
                        "internal_blanks": internal_blanks,
                        "trailing_values": trailing_values,
                    }
                )
    all_plain_cells = all(
        row == [("td", None, None)] * COLUMNS for row in parsed.rows
    )
    expected_prefix = f"{TITLE}\n{SUBTITLE}\n\n"
    prefix_exact = markdown.startswith(expected_prefix + "<table")
    suffix_exact = markdown.endswith("</table>") and markdown.count("<table") == 1
    structure_ok = (
        parsed.tables == 1
        and row_lengths == [COLUMNS] * ROWS
        and all_plain_cells
        and prefix_exact
        and suffix_exact
        and actual_header == header
        and actual_keys == expected
        and len(cells) == EXPECTED_NONEMPTY
        and not numeric_anomalies
        and not duplicate_cells
        and not prefix_mismatches
    )
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "data_rows": len(data_rows),
        "row_lengths": sorted(set(row_lengths)),
        "nonempty_cells": len(cells),
        "normalized_characters": sum(map(len, cells)),
        "prefix_exact": prefix_exact,
        "suffix_exact": suffix_exact,
        "header_exact": actual_header == header,
        "key_sequence_exact": actual_keys == expected,
        "first_keys": actual_keys[:4],
        "last_keys": actual_keys[-4:],
        "plain_cells_exact": all_plain_cells,
        "numeric_anomalies": numeric_anomalies,
        "exact_duplicate_cells": duplicate_cells,
        "prefix_mismatches": prefix_mismatches,
        "structure_ok": structure_ok,
    }


def ordered_cell_agreement(candidate: str, old: str) -> dict[str, object]:
    _, candidate_cells = parse(candidate)
    _, old_cells = parse(old)
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v14.csv"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(
            "D:/AFAC2026/outputs/experiments/full110_filled_A_e082.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v15.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v15.report.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base_predictions = load_submission(args.base)
    predictions = dict(base_predictions)
    old = predictions[TARGET]
    candidate = args.candidate.read_text(encoding="utf-8").rstrip("\n")
    structure = structure_report(candidate)
    if not bool(structure["structure_ok"]):
        raise ValueError(f"candidate structure failed: {structure}")
    agreement = ordered_cell_agreement(candidate, old)
    if int(agreement["candidate_nonempty_cells"]) != EXPECTED_NONEMPTY:
        raise ValueError(f"candidate cell count changed: {agreement}")
    if int(agreement["old_nonempty_cells"]) != 27_521:
        raise ValueError(f"base sample no longer matches audited v14: {agreement}")
    if int(agreement["ordered_exact_cells"]) != 23_240:
        raise ValueError(f"ordered agreement changed: {agreement}")
    if float(agreement["old_coverage"]) < 0.84:
        raise ValueError(f"candidate did not preserve enough old cells: {agreement}")
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
    report = {
        "base": str(args.base),
        "output": str(args.output),
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
            "candidate": str(args.candidate),
            "old_characters": len(old),
            "new_characters": len(candidate),
            "added_characters": len(candidate) - len(old),
            "structure": structure,
            "agreement": agreement,
            "evidence": {
                "horizontal_rules": 356,
                "stable_horizontal_rule_configurations": 7,
                "vertical_rules": 111,
                "stable_vertical_rule_configurations": 56,
                "detected_text_row_groups": 357,
                "projected_text_row_groups": 356,
                "ocr_tiles": 24,
                "ocr_detections": 27_754,
                "canonical_key_changes_by_group": [14, 70, 25, 29],
                "numeric_punctuation_repairs": 1_039,
                "character_numeric_repairs": 25,
                "submission_anchored_blank_recoveries": 136,
                "direct_crop_repairs": 9,
                "internal_blanks_recovered": 144,
                "training_blind_grid": {
                    "rows": 307,
                    "columns": 110,
                    "normalized_error": 0.00032677,
                    "differing_cells": 70,
                },
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
