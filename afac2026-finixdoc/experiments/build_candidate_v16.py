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
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402
from audit_two_triangular_integer_tables import (  # noqa: E402
    nonempty_cells,
    parse_tables,
    table_report,
)


TARGET = "4c2588e5-f850-4fb4-bc7f-8ac47d2418b0.jpg"
EXPECTED_NONEMPTY = 7_168


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


def structure_report(markdown: str) -> dict[str, object]:
    tables = parse_tables(markdown)
    outside = re.sub(
        r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S
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
    cells = nonempty_cells(markdown)
    structure_ok = (
        len(tables) == 2
        and not outside
        and bool(first["structure_ok"])
        and bool(second["structure_ok"])
        and len(cells) == EXPECTED_NONEMPTY
    )
    return {
        "tables": len(tables),
        "outside_text": outside,
        "nonempty_cells": len(cells),
        "first_table": first,
        "second_table": second,
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v15.csv"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(
            "D:/AFAC2026/outputs/experiments/rule_combined_A_4c2588.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v16.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v16.report.json"),
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
    if int(agreement["old_nonempty_cells"]) != 6_343:
        raise ValueError(f"base sample no longer matches audited v15: {agreement}")
    if int(agreement["ordered_exact_cells"]) != 6_291:
        raise ValueError(f"ordered agreement changed: {agreement}")
    if float(agreement["old_coverage"]) < 0.99:
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
                "first_table": {
                    "shape": [73, 72],
                    "horizontal_rules": 74,
                    "stable_horizontal_configurations": 72,
                    "exact_two_dimensional_configurations": 73,
                    "two_dimensional_configurations": 120,
                    "ocr_tiles": 8,
                    "ocr_detections": 2_771,
                    "detected_text_row_groups": 73,
                    "projected_text_row_groups": 71,
                },
                "second_table": {
                    "shape": [74, 67],
                    "horizontal_rules": 75,
                    "combined_horizontal_rules": 149,
                    "combined_stable_configurations": 425,
                    "inter_table_gap": 54,
                    "median_row_gap": 18,
                    "exact_two_dimensional_configurations": 62,
                    "two_dimensional_configurations": 120,
                    "ocr_tiles": 8,
                    "ocr_detections": 4_397,
                    "detected_text_row_groups": 74,
                    "projected_text_row_groups": 69,
                },
                "terminal_index": 106,
                "expected_nonempty_formula": "min(columns, 107 - row_key)",
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
