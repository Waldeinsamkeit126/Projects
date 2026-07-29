from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


TARGET = "aecf66d9-d361-4b7b-948a-e5e8693c4877.jpg"
FIXED_LABELS = ["交费期间", "性别", "投保年龄（周岁）"]
SPAN_LABEL = "保单年度末"
NUMBERED_CELLS = 104


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
    expected_lengths = [4, NUMBERED_CELLS, *([107] * 323)]
    expected_first = [
        ("td", "2", None),
        ("td", "2", None),
        ("td", "2", None),
        ("td", None, str(NUMBERED_CELLS)),
    ]
    expected_header = [
        [*FIXED_LABELS, SPAN_LABEL],
        [str(number) for number in range(1, NUMBERED_CELLS + 1)],
    ]
    actual_header = parsed.cell_text_rows[:2]
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "row_lengths": sorted(set(row_lengths)),
        "nonempty_cells": len(cells),
        "normalized_characters": sum(map(len, cells)),
        "header_exact": actual_header == expected_header,
        "structure_ok": (
            parsed.tables == 1
            and row_lengths == expected_lengths
            and parsed.rows[0] == expected_first
            and actual_header == expected_header
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v11.csv"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(
            "D:/AFAC2026/outputs/experiments/"
            "corner3_rule107_canonical_A_aecf.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v12.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v12.report.json"),
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
    if int(agreement["candidate_nonempty_cells"]) < 22_000:
        raise ValueError(f"candidate recovered too few cells: {agreement}")
    if int(agreement["old_nonempty_cells"]) > 2_100:
        raise ValueError(f"base sample no longer matches audited v11: {agreement}")
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
            "agreement": agreement,
            "evidence": {
                "horizontal_rules": 326,
                "vertical_rules": 108,
                "header_year_cells": NUMBERED_CELLS,
                "matching_training_template": (
                    "f5009a2d-b341-43f1-a9d3-d6f371606378.jpg"
                ),
                "training_normalized_text_error": 0.004952836292878504,
                "exact_header_grid_configurations": 32,
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
