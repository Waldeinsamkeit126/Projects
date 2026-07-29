from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


TARGET = "4752c7d7-df43-48fc-8e1c-b15b57a76a51.jpg"


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
    parsed = _TableParser()
    parsed.feed(markdown)
    row_lengths = list(map(len, parsed.rows))
    expected_lengths = [5, 99, *([103] * 263)]
    expected_first = [
        ("td", "2", None),
        ("td", "2", None),
        ("td", "2", None),
        ("td", "2", None),
        ("td", None, "99"),
    ]
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "row_lengths": sorted(set(row_lengths)),
        "structure_ok": (
            parsed.tables == 1
            and row_lengths == expected_lengths
            and parsed.rows[0] == expected_first
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v9.csv"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(
            "D:/AFAC2026/outputs/experiments/corner4_rule103_A_4752c7d7.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v10.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v10.report.json"),
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
    if len(candidate) < 100_000 or len(candidate) <= len(old) * 5:
        raise ValueError(
            "candidate did not recover the expected large amount of table content: "
            f"old={len(old)}, new={len(candidate)}"
        )
    predictions[TARGET] = candidate
    write_submission(data.submission_template, predictions, args.output)
    written = load_submission(args.output)
    changed_names = sorted(
        name
        for name, value in written.items()
        if value != base_predictions[name]
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
            "evidence": {
                "horizontal_rules": 266,
                "vertical_rules": 104,
                "header_year_cells": 99,
                "training_normalized_errors": [
                    0.0007725775627210995,
                    0.0010676829927559737,
                ],
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
