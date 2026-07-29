from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


TARGET = "bf21c4c0-cab4-4116-9b64-fe341dad80e1.jpg"
TITLE = "海港启明星尊享版终身寿险现金价值全表"
SUBTITLE = "（以1000元年交保险费为计算单位）"
FIXED_LABELS = ["保险期间", "交费期间", "年龄", "性别"]
YEAR_CELLS = 106
EXPECTED_GROUPS = {
    ("1", "男"): list(range(76)),
    ("1", "女"): list(range(76)),
    ("3", "男"): list(range(71)),
    ("3", "女"): list(range(71)),
    ("5", "男"): list(range(30)),
    ("5", "女"): list(range(29)),
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
    expected_header = [
        *FIXED_LABELS,
        *[f"第{number}保单年度末" for number in range(1, YEAR_CELLS + 1)],
    ]
    actual_header = parsed.cell_text_rows[0] if parsed.cell_text_rows else []
    groups: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    invalid_keys: list[dict[str, object]] = []
    duplicate_cells: list[dict[str, object]] = []
    for row_index, row in enumerate(parsed.cell_text_rows[1:], 1):
        if len(row) < 4:
            invalid_keys.append({"row": row_index, "keys": row})
            continue
        insurance, payment, age_text, gender = map(str.strip, row[:4])
        try:
            age = int(age_text)
        except ValueError:
            invalid_keys.append({"row": row_index, "keys": row[:4]})
            continue
        if insurance != "终身":
            invalid_keys.append({"row": row_index, "keys": row[:4]})
        groups[(payment, gender)].append(age)
        for column_index, cell in enumerate(row):
            tokens = cell.split()
            if len(tokens) > 1 and len(set(tokens)) == 1:
                duplicate_cells.append(
                    {"row": row_index, "column": column_index, "text": cell}
                )
    actual_groups = {key: value for key, value in groups.items()}
    group_sequences_exact = actual_groups == EXPECTED_GROUPS
    prefix_exact = markdown.startswith(f"{TITLE}\n{SUBTITLE}\n\n<table")
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "row_lengths": sorted(set(row_lengths)),
        "nonempty_cells": len(cells),
        "normalized_characters": sum(map(len, cells)),
        "prefix_exact": prefix_exact,
        "header_exact": actual_header == expected_header,
        "group_sequences_exact": group_sequences_exact,
        "group_counts": {
            f"{payment}-{gender}": len(ages)
            for (payment, gender), ages in sorted(actual_groups.items())
        },
        "invalid_keys": invalid_keys,
        "exact_duplicate_cells": duplicate_cells,
        "structure_ok": (
            parsed.tables == 1
            and row_lengths == [110] * 354
            and parsed.rows[0] == [("td", None, None)] * 110
            and prefix_exact
            and actual_header == expected_header
            and group_sequences_exact
            and not invalid_keys
            and not duplicate_cells
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v12.csv"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(
            "D:/AFAC2026/outputs/experiments/"
            "full110_canonical_dedup_A_bf21.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v13.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v13.report.json"),
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
    if int(agreement["candidate_nonempty_cells"]) < 27_300:
        raise ValueError(f"candidate recovered too few cells: {agreement}")
    if int(agreement["old_nonempty_cells"]) > 4_900:
        raise ValueError(f"base sample no longer matches audited v12: {agreement}")
    if float(agreement["old_coverage"]) < 0.93:
        raise ValueError(f"candidate did not preserve enough old cells: {agreement}")
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
                "vertical_rules": 111,
                "stable_110_column_configurations": 76,
                "tested_column_configurations": 85,
                "detected_text_row_groups": 357,
                "projected_text_row_groups": 356,
                "semantic_table_rows": 354,
                "training_template": (
                    "0878213b-66b1-412f-a50a-01b233ef840f.jpg"
                ),
                "training_grid_shape_exact": True,
                "training_normalized_text_error": 0.000326772976808455,
                "training_differing_cells": 70,
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
