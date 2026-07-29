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


TARGET = "81016aef-ec9c-495e-8eee-2dc0012027d7.jpg"
SHAPES = ((107, 66), (57, 73))
EXPECTED_NONEMPTY = (4_982, 3_930)
HEADER_LABEL = "保单年度末\\投保年龄"


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
            "submission must contain 100 unique rows: "
            f"rows={len(records)} unique={len(predictions)}"
        )
    return predictions


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


def clean_decimal(value: str) -> str:
    value = re.sub(r"\s+", "", value.strip()).replace(",", ".")
    if value.count(".") > 1:
        whole, fraction = value.rsplit(".", 1)
        value = whole.replace(".", "") + "." + fraction
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
        raise ValueError(f"not an unambiguous two-decimal OCR value: {value!r}")
    whole, fraction = value.split(".")
    return f"{int(whole)}.{fraction}"


def canonical_from_digits(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 3:
        return None
    return f"{int(digits[:-2])}.{digits[-2:]}"


def expected_end(columns: int, year: int) -> int:
    return min(columns, 108 - year)


def clean_ocr(
    markdown: str, table_index: int
) -> tuple[list[list[str]], dict[str, object]]:
    expected_rows, columns = SHAPES[table_index]
    parsed = _TableParser()
    parsed.feed(markdown)
    if parsed.tables != 1:
        raise ValueError(f"OCR table {table_index + 1} count changed: {parsed.tables}")
    if len(parsed.cell_text_rows) != expected_rows:
        raise ValueError(
            f"OCR table {table_index + 1} row count changed: "
            f"{len(parsed.cell_text_rows)}"
        )
    if any(len(row) != columns for row in parsed.cell_text_rows):
        raise ValueError(f"OCR table {table_index + 1} is not uniformly {columns} columns")

    raw_nonempty = sum(
        bool(value.strip()) for row in parsed.cell_text_rows for value in row
    )
    if raw_nonempty != EXPECTED_NONEMPTY[table_index]:
        raise ValueError(
            f"OCR table {table_index + 1} nonempty count changed: {raw_nonempty}"
        )

    cleaned: list[list[str]] = [
        [HEADER_LABEL, *[str(age) for age in range(columns - 1)]]
    ]
    punctuation_repairs: list[dict[str, object]] = []
    for year, raw in enumerate(parsed.cell_text_rows[1:], 1):
        end = expected_end(columns, year)
        internal_blanks = [
            column for column, value in enumerate(raw[:end]) if not value.strip()
        ]
        overflow = [
            [column, value]
            for column, value in enumerate(raw[end:], end)
            if value.strip()
        ]
        if internal_blanks or overflow:
            raise ValueError(
                f"table {table_index + 1} year {year} violates triangular prefix: "
                f"internal={internal_blanks} overflow={overflow}"
            )
        if raw[0].strip() != str(year):
            raise ValueError(
                f"table {table_index + 1} key changed at year {year}: {raw[0]!r}"
            )
        numeric: list[str] = []
        for column, value in enumerate(raw[1:end], 1):
            canonical = clean_decimal(value)
            if canonical != value.strip():
                punctuation_repairs.append(
                    {
                        "row": year,
                        "column": column,
                        "old": value,
                        "new": canonical,
                    }
                )
            numeric.append(canonical)
        row = [str(year), *numeric, *([""] * (columns - end))]
        if len(row) != columns:
            raise AssertionError("cleaning changed table width")
        cleaned.append(row)
    return cleaned, {
        "raw_nonempty_cells": raw_nonempty,
        "punctuation_repairs": len(punctuation_repairs),
        "punctuation_repair_details": punctuation_repairs,
        "header_reconstructed": [HEADER_LABEL, "0", str(columns - 2)],
        "keys_reconstructed": ["1", str(expected_rows - 1)],
    }


def serialize_table(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def validate_table(
    parsed: _TableParser, table_index: int
) -> dict[str, object]:
    expected_rows, columns = SHAPES[table_index]
    row_lengths = list(map(len, parsed.cell_text_rows))
    header = [HEADER_LABEL, *[str(age) for age in range(columns - 1)]]
    key_sequence = [row[0] for row in parsed.cell_text_rows[1:]]
    expected_keys = [str(year) for year in range(1, expected_rows)]
    prefix_mismatches: list[dict[str, object]] = []
    numeric_anomalies: list[dict[str, object]] = []
    for year, row in enumerate(parsed.cell_text_rows[1:], 1):
        end = expected_end(columns, year)
        internal = [column for column, value in enumerate(row[:end]) if not value]
        overflow = [
            [column, value]
            for column, value in enumerate(row[end:], end)
            if value
        ]
        if internal or overflow:
            prefix_mismatches.append(
                {"year": year, "internal": internal, "overflow": overflow}
            )
        for column, value in enumerate(row[1:end], 1):
            if not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
                numeric_anomalies.append(
                    {"year": year, "column": column, "value": value}
                )
    nonempty = sum(
        bool(value.strip()) for row in parsed.cell_text_rows for value in row
    )
    plain_cells = all(
        row == [("td", None, None)] * columns for row in parsed.rows
    )
    structure_ok = (
        len(parsed.rows) == expected_rows
        and row_lengths == [columns] * expected_rows
        and parsed.cell_text_rows[0] == header
        and key_sequence == expected_keys
        and nonempty == EXPECTED_NONEMPTY[table_index]
        and plain_cells
        and not prefix_mismatches
        and not numeric_anomalies
    )
    return {
        "rows": len(parsed.rows),
        "columns": sorted(set(row_lengths)),
        "nonempty_cells": nonempty,
        "header_exact": parsed.cell_text_rows[0] == header,
        "key_sequence_exact": key_sequence == expected_keys,
        "first_keys": key_sequence[:4],
        "last_keys": key_sequence[-4:],
        "plain_cells_exact": plain_cells,
        "prefix_mismatches": prefix_mismatches,
        "numeric_anomalies": numeric_anomalies,
        "structure_ok": structure_ok,
    }


def validate_candidate(markdown: str) -> dict[str, object]:
    tables = parse_tables(markdown)
    outside = re.sub(
        r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S
    )
    outside_lines = [line.strip() for line in outside.splitlines() if line.strip()]
    expected_outside = ["性别 男性", "保险期间 106", "交费期间 1", "性别 女性"]
    reports = [
        validate_table(table, table_index)
        for table_index, table in enumerate(tables)
    ] if len(tables) == 2 else []
    structure_ok = (
        len(tables) == 2
        and outside_lines == expected_outside
        and all(bool(report["structure_ok"]) for report in reports)
    )
    return {
        "tables": len(tables),
        "outside_lines": outside_lines,
        "outside_exact": outside_lines == expected_outside,
        "table_reports": reports,
        "structure_ok": structure_ok,
    }


def cloud_agreement(
    old: str, candidate_tables: list[list[list[str]]]
) -> dict[str, object]:
    old_tables = parse_tables(old)
    if len(old_tables) != 2:
        raise ValueError(f"old prediction table count changed: {len(old_tables)}")
    expected_ranges = ((5, 105), (7, 56))
    table_reports: list[dict[str, object]] = []
    all_disagreements: list[dict[str, object]] = []
    total_compared = 0
    total_exact = 0
    for table_index, (old_table, candidate, year_range) in enumerate(
        zip(old_tables, candidate_tables, expected_ranges)
    ):
        by_key = {
            row[0].strip(): [value for value in row if value.strip()]
            for row in old_table.cell_text_rows
        }
        compared = 0
        exact = 0
        count_mismatches: list[dict[str, int]] = []
        disagreements: list[dict[str, object]] = []
        for year in range(year_range[0], year_range[1] + 1):
            local = candidate[year]
            local_nonempty = [value for value in local if value]
            cloud = by_key.get(str(year))
            if cloud is None or len(cloud) != len(local_nonempty):
                count_mismatches.append(
                    {
                        "year": year,
                        "expected": len(local_nonempty),
                        "cloud": 0 if cloud is None else len(cloud),
                    }
                )
                continue
            for column, (local_value, cloud_value) in enumerate(
                zip(local_nonempty[1:], cloud[1:]), 1
            ):
                cloud_clean = canonical_from_digits(cloud_value)
                if cloud_clean is None:
                    continue
                compared += 1
                if local_value == cloud_clean:
                    exact += 1
                else:
                    item = {
                        "table": table_index + 1,
                        "year": year,
                        "column": column,
                        "local": local_value,
                        "cloud": cloud_clean,
                        "cloud_raw": cloud_value,
                        "selected": "local",
                    }
                    disagreements.append(item)
                    all_disagreements.append(item)
        total_compared += compared
        total_exact += exact
        table_reports.append(
            {
                "old_rows": len(old_table.rows),
                "old_widths": sorted(set(map(len, old_table.rows))),
                "year_range": list(year_range),
                "count_mismatches": count_mismatches,
                "compared_numeric_cells": compared,
                "exact_numeric_cells": exact,
                "disagreements": disagreements,
            }
        )
    return {
        "tables": table_reports,
        "compared_numeric_cells": total_compared,
        "exact_numeric_cells": total_exact,
        "exact_numeric_rate": total_exact / max(1, total_compared),
        "disagreement_cells": len(all_disagreements),
        "disagreements": all_disagreements,
        "selection": "local retained after row-sequence review",
    }


def training_validation(
    ocr_paths: tuple[Path, Path], gt_path: Path
) -> dict[str, object]:
    gt_tables = parse_tables(gt_path.read_text(encoding="utf-8"))
    if len(gt_tables) != 2:
        raise ValueError("training GT table count changed")
    reports: list[dict[str, object]] = []
    total = 0
    exact = 0
    disagreements: list[dict[str, object]] = []
    for table_index, (ocr_path, gt) in enumerate(zip(ocr_paths, gt_tables)):
        parsed = _TableParser()
        parsed.feed(ocr_path.read_text(encoding="utf-8"))
        if len(parsed.cell_text_rows) != len(gt.cell_text_rows):
            raise ValueError("training OCR row count changed")
        table_total = 0
        table_exact = 0
        table_disagreements: list[dict[str, object]] = []
        for row_index, (ocr_row, gt_row) in enumerate(
            zip(parsed.cell_text_rows[1:], gt.cell_text_rows[1:]), 1
        ):
            for column, (ocr_value, gt_value) in enumerate(
                zip(ocr_row[1:], gt_row[1:]), 1
            ):
                if not gt_value.strip():
                    if ocr_value.strip():
                        raise ValueError("training OCR put text into a GT blank cell")
                    continue
                table_total += 1
                left = canonical_from_digits(ocr_value)
                right = canonical_from_digits(gt_value)
                if left == right:
                    table_exact += 1
                else:
                    item = {
                        "table": table_index + 1,
                        "row": row_index,
                        "column": column,
                        "ocr": left,
                        "ocr_raw": ocr_value,
                        "gt": right,
                    }
                    table_disagreements.append(item)
                    disagreements.append(item)
        total += table_total
        exact += table_exact
        reports.append(
            {
                "numeric_cells": table_total,
                "exact_numeric_cells": table_exact,
                "exact_numeric_rate": table_exact / max(1, table_total),
                "disagreements": table_disagreements,
            }
        )
    result = {
        "image": "1b8718d0-ea4f-4085-a853-9fa3d5a57ada.jpg",
        "tables": reports,
        "numeric_cells": total,
        "exact_numeric_cells": exact,
        "exact_numeric_rate": exact / max(1, total),
        "disagreements": disagreements,
        "validation_ok": total == 8_136 and exact >= 8_130,
    }
    if not result["validation_ok"]:
        raise ValueError(f"training calibration failed: {result}")
    return result


def grid_probe_validation(paths: tuple[Path, Path]) -> dict[str, object]:
    expected = (
        {
            (107, 66): 81,
            (106, 66): 12,
            (108, 66): 0,
            (107, 65): 0,
            (107, 67): 0,
        },
        {
            (57, 73): 90,
            (56, 73): 12,
            (58, 73): 0,
            (57, 72): 0,
            (57, 74): 0,
        },
    )
    reports: list[dict[str, object]] = []
    for path, expected_items in zip(paths, expected):
        raw = json.loads(path.read_text(encoding="utf-8"))
        actual = {
            tuple(int(value) for value in item["shape"]): int(item["successes"])
            for item in raw["items"]
        }
        if actual != expected_items:
            raise ValueError(
                f"rule-grid probe changed for {path}: "
                f"expected={expected_items} actual={actual}"
            )
        target = next(iter(expected_items))
        if actual[target] <= max(
            successes for shape, successes in actual.items() if shape != target
        ):
            raise ValueError(f"target grid is not dominant for {path}")
        reports.append(
            {
                "path": str(path),
                "configurations_per_shape": 120,
                "target_shape": list(target),
                "target_successes": actual[target],
                "competing_shapes": [
                    {"shape": list(shape), "successes": successes}
                    for shape, successes in actual.items()
                    if shape != target
                ],
            }
        )
    return {"tables": reports, "validation_ok": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v19.csv"),
    )
    parser.add_argument("--ocr-table1", type=Path, required=True)
    parser.add_argument("--ocr-table2", type=Path, required=True)
    parser.add_argument("--training-ocr-table1", type=Path, required=True)
    parser.add_argument("--training-ocr-table2", type=Path, required=True)
    parser.add_argument("--training-gt", type=Path, required=True)
    parser.add_argument("--grid-report-table1", type=Path, required=True)
    parser.add_argument("--grid-report-table2", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(
            "D:/AFAC2026/outputs/experiments/"
            "rule107x66_57x73_clean_A_81016.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v20.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v20.report.json"),
    )
    args = parser.parse_args()

    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base = load_submission(args.base)
    old = base[TARGET]
    table1, cleanup1 = clean_ocr(
        args.ocr_table1.read_text(encoding="utf-8"), 0
    )
    table2, cleanup2 = clean_ocr(
        args.ocr_table2.read_text(encoding="utf-8"), 1
    )
    candidate = (
        "性别 男性\n\n"
        + serialize_table(table1)
        + "\n\n保险期间 106\n交费期间 1\n性别 女性\n\n"
        + serialize_table(table2)
    )
    structure = validate_candidate(candidate)
    if not structure["structure_ok"]:
        raise ValueError(f"candidate structure failed: {structure}")
    agreement = cloud_agreement(old, [table1, table2])
    calibration = training_validation(
        (args.training_ocr_table1, args.training_ocr_table2), args.training_gt
    )
    grid_probes = grid_probe_validation(
        (args.grid_report_table1, args.grid_report_table2)
    )

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
            "metadata_lines": [
                "性别 男性",
                "保险期间 106",
                "交费期间 1",
                "性别 女性",
            ],
            "cleanup": [cleanup1, cleanup2],
            "structure": structure,
            "training_calibration": calibration,
            "cloud_agreement": agreement,
            "grid_probe_validation": grid_probes,
            "grid_evidence": {
                "semantic_shapes": [[107, 66], [57, 73]],
                "physical_shapes_with_title": [[108, 66], [58, 73]],
                "horizontal_rules": [108, 58],
                "vertical_rules": [67, 74],
                "detected_text_row_groups": [107, 57],
                "projected_text_row_groups": [107, 57],
                "ocr_detections": [4982, 3930],
                "theoretical_nonempty": [4982, 3930],
                "input_sha256": {
                    "ocr_table1": hashlib.sha256(
                        args.ocr_table1.read_bytes()
                    ).hexdigest(),
                    "ocr_table2": hashlib.sha256(
                        args.ocr_table2.read_bytes()
                    ).hexdigest(),
                    "training_ocr_table1": hashlib.sha256(
                        args.training_ocr_table1.read_bytes()
                    ).hexdigest(),
                    "training_ocr_table2": hashlib.sha256(
                        args.training_ocr_table2.read_bytes()
                    ).hexdigest(),
                },
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
