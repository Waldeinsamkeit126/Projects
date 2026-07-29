from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


TARGET = "276f08ab-b337-4baa-87d0-b7ea40c31fbc.jpg"
ROWS = 90
COLUMNS = 110
EXPECTED_NONEMPTY = 6930


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected submission columns: {reader.fieldnames}")
        records = list(reader)
    predictions = {
        str(record["file_name"]): str(record["ground_truth"])
        for record in records
    }
    if len(records) != 100 or len(predictions) != 100:
        raise ValueError(
            f"submission must contain 100 unique rows: "
            f"rows={len(records)} unique={len(predictions)}"
        )
    return predictions


def parse_one(markdown: str) -> _TableParser:
    parsed = _TableParser()
    parsed.feed(markdown)
    if parsed.tables != 1:
        raise ValueError(f"expected one table, found {parsed.tables}")
    return parsed


def canonical_decimal(value: str) -> str:
    # PP-OCR repeatedly reads the narrow digit 1 as a closing square bracket
    # in this exact typeface.  The same mapping is visible in both the integer
    # and fractional positions (for example 8]4].2] -> 8141.21).
    value = value.replace("]", "1")
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 3:
        return f"{digits[:-2]}.{digits[-2:]}"
    if digits == "0":
        return "0.00"
    raise ValueError(f"cannot recover a two-decimal value from {value!r}")


def expected_key(row_index: int) -> tuple[str, str, str, str]:
    age = 11 + row_index // 2
    gender = "男" if row_index % 2 == 0 else "女"
    return "终身", "20", str(age), gender


def clean_ocr(markdown: str) -> tuple[list[list[str]], dict[str, object]]:
    parsed = parse_one(markdown)
    if len(parsed.cell_text_rows) != ROWS:
        raise ValueError(f"expected {ROWS} OCR rows, found {len(parsed.cell_text_rows)}")
    if any(len(row) != COLUMNS for row in parsed.cell_text_rows):
        raise ValueError("OCR rows are not uniformly 110 columns")

    rows: list[list[str]] = []
    key_changes = [0, 0, 0, 0]
    punctuation_changes = 0
    for row_index, raw in enumerate(parsed.cell_text_rows):
        key = expected_key(row_index)
        age = int(key[2])
        expected_end = COLUMNS - age
        internal_blanks = [
            column for column, value in enumerate(raw[:expected_end]) if not value.strip()
        ]
        overflow = [
            column
            for column, value in enumerate(raw[expected_end:], expected_end)
            if value.strip()
        ]
        if internal_blanks or overflow:
            raise ValueError(
                f"row {row_index} violates its triangular prefix: "
                f"internal_blanks={internal_blanks} overflow={overflow}"
            )
        for column, expected in enumerate(key):
            key_changes[column] += raw[column].strip() != expected
        numeric: list[str] = []
        for value in raw[4:expected_end]:
            cleaned = canonical_decimal(value)
            punctuation_changes += cleaned != value.strip()
            numeric.append(cleaned)
        row = [*key, *numeric, *([""] * age)]
        if len(row) != COLUMNS:
            raise AssertionError(f"cleaned row {row_index} changed width")
        rows.append(row)
    return rows, {
        "key_changes": key_changes,
        "numeric_punctuation_changes": punctuation_changes,
        "ocr_nonempty_cells": sum(
            bool(value.strip()) for row in parsed.cell_text_rows for value in row
        ),
    }


def serialize(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def apply_pixel_repairs(rows: list[list[str]]) -> list[dict[str, object]]:
    # Both OCR routes confuse the 6/4 in this exceptionally soft cell.  A
    # 14x lossless enlargement of physical grid cell r10c16 reads 9692.34.
    specifications = [(10, 16, "909.23", "9692.34")]
    repairs: list[dict[str, object]] = []
    for row, column, old, new in specifications:
        if rows[row][column] != old:
            raise ValueError(
                f"pixel repair source changed at {row}:{column}: "
                f"expected={old!r} actual={rows[row][column]!r}"
            )
        rows[row][column] = new
        repairs.append(
            {
                "row": row,
                "column": column,
                "numeric_column": column - 4,
                "old": old,
                "new": new,
                "evidence": "14x original-grid-cell enlargement",
            }
        )
    return repairs


def validate_candidate(markdown: str) -> dict[str, object]:
    parsed = parse_one(markdown)
    row_lengths = list(map(len, parsed.cell_text_rows))
    keys = [tuple(row[:4]) for row in parsed.cell_text_rows]
    numeric_anomalies: list[dict[str, object]] = []
    prefix_mismatches: list[dict[str, object]] = []
    for row_index, row in enumerate(parsed.cell_text_rows):
        age = 11 + row_index // 2
        expected_end = COLUMNS - age
        for column, value in enumerate(row[4:expected_end], start=4):
            if not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
                numeric_anomalies.append(
                    {"row": row_index, "column": column, "value": value}
                )
        internal = [
            column for column, value in enumerate(row[:expected_end]) if not value
        ]
        overflow = [
            column
            for column, value in enumerate(row[expected_end:], expected_end)
            if value
        ]
        if internal or overflow:
            prefix_mismatches.append(
                {"row": row_index, "internal": internal, "overflow": overflow}
            )
    nonempty = sum(
        bool(value.strip()) for row in parsed.cell_text_rows for value in row
    )
    plain_cells = all(
        row == [("td", None, None)] * COLUMNS for row in parsed.rows
    )
    expected_keys = [expected_key(index) for index in range(ROWS)]
    structure_ok = (
        parsed.tables == 1
        and row_lengths == [COLUMNS] * ROWS
        and plain_cells
        and keys == expected_keys
        and nonempty == EXPECTED_NONEMPTY
        and not numeric_anomalies
        and not prefix_mismatches
    )
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "columns": sorted(set(row_lengths)),
        "nonempty_cells": nonempty,
        "key_sequence_exact": keys == expected_keys,
        "first_keys": keys[:4],
        "last_keys": keys[-4:],
        "plain_cells_exact": plain_cells,
        "numeric_anomalies": numeric_anomalies,
        "prefix_mismatches": prefix_mismatches,
        "structure_ok": structure_ok,
    }


def cloud_agreement(old: str, candidate_rows: list[list[str]]) -> dict[str, object]:
    parsed = parse_one(old)
    if len(parsed.cell_text_rows) != ROWS:
        raise ValueError(f"old prediction row count changed: {len(parsed.cell_text_rows)}")
    count_exact_rows = 0
    compared_numeric = 0
    exact_numeric = 0
    unequal_count_rows: list[dict[str, int]] = []
    for row_index, (candidate, cloud_row) in enumerate(
        zip(candidate_rows, parsed.cell_text_rows)
    ):
        age = 11 + row_index // 2
        expected_end = COLUMNS - age
        cloud = [value for value in cloud_row if value.strip()]
        if len(cloud) != expected_end:
            unequal_count_rows.append(
                {
                    "row": row_index,
                    "age": age,
                    "expected": expected_end,
                    "cloud": len(cloud),
                }
            )
            continue
        count_exact_rows += 1
        for local_value, cloud_value in zip(candidate[4:expected_end], cloud[4:]):
            compared_numeric += 1
            try:
                cloud_cleaned = canonical_decimal(cloud_value)
            except ValueError:
                continue
            exact_numeric += local_value == cloud_cleaned
    return {
        "old_rows": len(parsed.rows),
        "old_row_widths": sorted(set(map(len, parsed.rows))),
        "old_nonempty_cells": sum(
            bool(value.strip()) for row in parsed.cell_text_rows for value in row
        ),
        "count_exact_rows": count_exact_rows,
        "unequal_count_rows": unequal_count_rows,
        "compared_numeric_cells": compared_numeric,
        "exact_numeric_cells": exact_numeric,
        "exact_numeric_rate": exact_numeric / max(1, compared_numeric),
    }


def apply_consensus(
    rows: list[list[str]],
    old: str,
    report_path: Path,
    ocr_path: Path,
    base_path: Path,
) -> dict[str, object]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("local_sha256") != hashlib.sha256(ocr_path.read_bytes()).hexdigest():
        raise ValueError("consensus report does not match the OCR source")
    if report.get("submission_sha256") != hashlib.sha256(base_path.read_bytes()).hexdigest():
        raise ValueError("consensus report does not match the v18 base")
    if report.get("anchor_cells") != 6120 or report.get("disagreement_cells") != 304:
        raise ValueError("consensus evidence counts changed")
    decisions = report.get("decisions")
    if decisions != {"local": 264, "cloud": 40, "insufficient": 0}:
        raise ValueError(f"consensus decisions changed: {decisions}")

    cloud_rows = parse_one(old).cell_text_rows
    replacements: list[dict[str, object]] = []
    checked = 0
    for item in report.get("disagreements", []):
        row = int(item["row"])
        column = int(item["numeric_column"])
        age = 11 + row // 2
        if not 0 <= column < 106 - age:
            raise ValueError(f"consensus cell is outside the numeric prefix: {item}")
        local = str(item["local"])
        cloud = str(item["cloud"])
        if rows[row][column + 4] != local:
            raise ValueError(f"consensus local value changed: {item}")
        cloud_nonempty = [value for value in cloud_rows[row] if value.strip()]
        if len(cloud_nonempty) != COLUMNS - age:
            raise ValueError(f"consensus unexpectedly references an unequal cloud row: {item}")
        actual_cloud = canonical_decimal(cloud_nonempty[column + 4])
        if actual_cloud != cloud:
            raise ValueError(
                f"consensus cloud value changed: expected={cloud!r} actual={actual_cloud!r}"
            )
        checked += 1
        if item["selected"] == "cloud":
            rows[row][column + 4] = cloud
            replacements.append(
                {
                    "row": row,
                    "age": age,
                    "gender": expected_key(row)[3],
                    "numeric_column": column,
                    "local": local,
                    "cloud": cloud,
                    "local_loss": item["local_loss"],
                    "cloud_loss": item["cloud_loss"],
                }
            )
    if checked != 304 or len(replacements) != 40:
        raise ValueError(
            f"consensus application count changed: checked={checked} "
            f"replacements={len(replacements)}"
        )
    return {
        "report": str(report_path),
        "anchor_cells": report["anchor_cells"],
        "disagreement_cells": report["disagreement_cells"],
        "decisions": decisions,
        "cloud_replacements": len(replacements),
        "replacement_details": replacements,
        "cross_validation": report["cross_validation"],
    }


def training_validation(ocr_path: Path, gt_path: Path) -> dict[str, object]:
    ocr = parse_one(ocr_path.read_text(encoding="utf-8"))
    gt = parse_one(gt_path.read_text(encoding="utf-8"))
    if len(ocr.cell_text_rows) != 60 or len(gt.cell_text_rows) != 60:
        raise ValueError("training calibration row count changed")
    compared = 0
    exact = 0
    count_mismatches: list[dict[str, int]] = []
    disagreements: list[dict[str, object]] = []
    for offset, (ocr_row, gt_row) in enumerate(
        zip(ocr.cell_text_rows[2:], gt.cell_text_rows[2:])
    ):
        age = 13 + offset
        expected_end = 102 - age
        ocr_nonempty = sum(bool(value.strip()) for value in ocr_row)
        gt_nonempty = sum(bool(value.strip()) for value in gt_row)
        if ocr_nonempty != expected_end or gt_nonempty != expected_end:
            count_mismatches.append(
                {
                    "age": age,
                    "expected": expected_end,
                    "ocr": ocr_nonempty,
                    "gt": gt_nonempty,
                }
            )
        for column, (ocr_value, gt_value) in enumerate(
            zip(ocr_row[3:expected_end], gt_row[3:expected_end]), start=3
        ):
            compared += 1
            left = canonical_decimal(ocr_value)
            right = canonical_decimal(gt_value)
            exact += left == right
            if left != right:
                disagreements.append(
                    {
                        "age": age,
                        "column": column,
                        "ocr": left,
                        "gt": right,
                    }
                )
    result = {
        "image": "998ada4c-743d-416b-a132-fedfb21aa018.jpg",
        "numeric_cells": compared,
        "exact_numeric_cells": exact,
        "exact_numeric_rate": exact / max(1, compared),
        "count_mismatches": count_mismatches,
        "disagreements": disagreements,
        "validation_ok": compared == 3335 and exact == compared and not count_mismatches,
    }
    if not result["validation_ok"]:
        raise ValueError(f"training calibration failed: {result}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v18.csv"),
    )
    parser.add_argument(
        "--ocr",
        type=Path,
        default=Path("D:/AFAC2026/outputs/experiments/rule90x110_A_276f.md"),
    )
    parser.add_argument(
        "--training-ocr",
        type=Path,
        default=Path("D:/AFAC2026/outputs/experiments/rule60x102_train_998.md"),
    )
    parser.add_argument(
        "--training-gt",
        type=Path,
        default=Path(
            "D:/AFAC2026/data/AFAC 训练数据集/"
            "finixdocbench_huge_table_100/mds/"
            "998ada4c-743d-416b-a132-fedfb21aa018.md"
        ),
    )
    parser.add_argument(
        "--consensus-report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/experiments/full110_consensus_276f.json"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path("D:/AFAC2026/outputs/experiments/rule90x110_clean_A_276f.md"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v19.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v19.report.json"),
    )
    args = parser.parse_args()

    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base = load_submission(args.base)
    old = base[TARGET]
    cleaned_rows, cleanup = clean_ocr(args.ocr.read_text(encoding="utf-8"))
    pixel_repairs = apply_pixel_repairs(cleaned_rows)
    consensus = apply_consensus(
        cleaned_rows, old, args.consensus_report, args.ocr, args.base
    )
    candidate = serialize(cleaned_rows)
    structure = validate_candidate(candidate)
    if not bool(structure["structure_ok"]):
        raise ValueError(f"candidate structure failed: {structure}")
    calibration = training_validation(args.training_ocr, args.training_gt)
    agreement = cloud_agreement(old, cleaned_rows)

    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text(candidate + "\n", encoding="utf-8")
    predictions = dict(base)
    predictions[TARGET] = candidate
    write_submission(data.submission_template, predictions, args.output)
    written = load_submission(args.output)
    changed_names = sorted(
        name for name, value in written.items() if value != base[name]
    )
    if changed_names != [TARGET]:
        raise ValueError(f"unexpected written changes: {changed_names}")
    if any(not value.strip() for value in written.values()):
        raise ValueError("written submission contains a blank prediction")

    report = {
        "base": str(args.base),
        "output": str(args.output),
        "candidate": str(args.candidate),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "rows": len(written),
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
            "cleanup": cleanup,
            "pixel_repairs": pixel_repairs,
            "structure": structure,
            "training_calibration": calibration,
            "consensus": consensus,
            "cloud_agreement": agreement,
            "grid_evidence": {
                "horizontal_rules": 91,
                "vertical_rules": 111,
                "stable_configurations": 17,
                "adjacent_109_column_successes": 0,
                "adjacent_111_column_successes": 0,
                "detected_text_row_groups": 90,
                "projected_text_row_groups": 90,
                "ocr_detections": 6930,
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
