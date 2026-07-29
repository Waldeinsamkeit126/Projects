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


TARGET = "bac0aeac-2cea-49c3-8714-d8f8753afcde.jpg"
ROWS = 359
COLUMNS = 110


def expected_keys() -> list[tuple[str, str, str, str]]:
    keys: list[tuple[str, str, str, str]] = []
    keys.append(("终身", "5", "34", "女"))
    for age in range(35, 66):
        keys.extend(
            [
                ("终身", "5", str(age), "男"),
                ("终身", "5", str(age), "女"),
            ]
        )
    for payment, maximum_age in (("10", 65), ("15", 55), ("20", 25)):
        for age in range(maximum_age + 1):
            keys.extend(
                [
                    ("终身", payment, str(age), "男"),
                    ("终身", payment, str(age), "女"),
                ]
            )
    if len(keys) != ROWS:
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
    expected = expected_keys()
    actual_keys = [tuple(map(str.strip, row[:4])) for row in parsed.cell_text_rows]
    numeric_anomalies: list[dict[str, object]] = []
    duplicate_cells: list[dict[str, object]] = []
    nonempty_mismatches: list[dict[str, object]] = []
    for row_index, row in enumerate(parsed.cell_text_rows):
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
            nonempty = sum(bool(cell.strip()) for cell in row)
            if nonempty != COLUMNS - age:
                nonempty_mismatches.append(
                    {
                        "row": row_index,
                        "age": age,
                        "expected": COLUMNS - age,
                        "actual": nonempty,
                    }
                )
    all_plain_cells = all(
        row == [("td", None, None)] * COLUMNS for row in parsed.rows
    )
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "row_lengths": sorted(set(row_lengths)),
        "nonempty_cells": len(cells),
        "normalized_characters": sum(map(len, cells)),
        "key_sequence_exact": actual_keys == expected,
        "first_keys": actual_keys[:4],
        "last_keys": actual_keys[-4:],
        "plain_cells_exact": all_plain_cells,
        "numeric_anomalies": numeric_anomalies,
        "exact_duplicate_cells": duplicate_cells,
        "nonempty_mismatches": nonempty_mismatches,
        "structure_ok": (
            parsed.tables == 1
            and row_lengths == [COLUMNS] * ROWS
            and all_plain_cells
            and actual_keys == expected
            and len(cells) == 28_336
            and not numeric_anomalies
            and not duplicate_cells
            and not nonempty_mismatches
        ),
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v13.csv"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(
            "D:/AFAC2026/outputs/experiments/full110_decimal_A_bac0.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v14.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v14.report.json"),
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
    if int(agreement["candidate_nonempty_cells"]) != 28_336:
        raise ValueError(f"candidate cell count changed: {agreement}")
    if int(agreement["old_nonempty_cells"]) != 13_308:
        raise ValueError(f"base sample no longer matches audited v13: {agreement}")
    if float(agreement["old_coverage"]) < 0.91:
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
                "horizontal_rules": 360,
                "stable_horizontal_rule_configurations": 252,
                "vertical_rules": 111,
                "stable_vertical_rule_configurations": 59,
                "detected_text_row_groups": 359,
                "projected_text_row_groups": 359,
                "ocr_tiles": 63,
                "ocr_detections": 28_336,
                "decimal_commas_normalized": 219,
                "old_exact_cells_gained_after_decimal_normalization": 84,
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
