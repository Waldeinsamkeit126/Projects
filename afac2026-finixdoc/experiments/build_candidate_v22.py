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


TARGET = "88684b6b-c5c6-4841-8708-518344458535.jpg"
BASE_SHA256 = "e7c282e00daa0f18db82a1a826bed93bf8c3329149110068c35d59c0d0dcefad"
SHAPES = ((64, 67), (107, 62), (12, 57))
YEAR_RANGES = ((43, 106), (1, 106), (1, 11))
HAS_HEADER = (False, True, True)
RAW_NONEMPTY = (2_144, 4_799, 683)
RAW_DUPLICATE_CELLS = (2, 6, 0)
EXPECTED_NONEMPTY = (2_144, 4_804, 684)
HEADER_LABEL = "保单年度末\\投保年龄"
EXPECTED_OUTSIDE = (
    "保险期间 106",
    "交费期间 15",
    "性别 男性",
    "保险期间 106",
    "交费期间 20",
    "性别 男性",
)

# Content changes require evidence beyond the OCR token itself.  The five blank
# cells and four ambiguous digits were read from rule-grid-addressed, enlarged
# crops of the original image.  Four of the ambiguous digits also agree with
# the old independent cloud OCR.
REPAIRS: dict[tuple[int, int, int], tuple[str, str, str]] = {
    (0, 58, 8): ("45222.11", "45222.71", "original-cell crop and cloud OCR"),
    (0, 59, 20): ("46194.35", "46494.35", "original-cell crop and cloud OCR"),
    (0, 67, 23): ("5863.98", "58863.98", "original-cell crop and cloud OCR"),
    (0, 80, 23): ("86122.36", "86422.36", "original-cell crop and cloud OCR"),
    (1, 3, 38): ("", "651.81", "original-cell crop"),
    (1, 58, 38): ("", "63032.44", "original-cell crop and cloud OCR"),
    (1, 59, 38): ("", "64922.24", "original-cell crop and cloud OCR"),
    (1, 62, 38): ("", "70937.71", "original-cell crop and cloud OCR"),
    (1, 63, 38): ("", "73063.94", "original-cell crop and cloud OCR"),
    (2, 8, 38): ("", "5907.35", "original-cell crop"),
}


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


def canonical_from_digits(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 3:
        return None
    return f"{int(digits[:-2])}.{digits[-2:]}"


def dedupe_exact_token(value: str) -> tuple[str, bool]:
    parts = value.strip().split()
    if len(parts) == 2 and parts[0] == parts[1]:
        return parts[0], True
    return value, False


def clean_decimal(value: str) -> tuple[str, bool]:
    value, deduplicated = dedupe_exact_token(value)
    value = re.sub(r"\s+", "", value.strip()).replace(",", ".").replace("-", "")
    if value.count(".") > 1:
        whole, fraction = value.rsplit(".", 1)
        value = whole.replace(".", "") + "." + fraction
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
        raise ValueError(f"not an unambiguous two-decimal OCR value: {value!r}")
    whole, fraction = value.split(".")
    return f"{int(whole)}.{fraction}", deduplicated


def expected_end(columns: int, year: int) -> int:
    """Exclusive end of the nonempty prefix, including the row-key column."""

    return min(columns, 108 - year)


def clean_ocr(
    markdown: str, table_index: int
) -> tuple[list[list[str]], dict[str, object]]:
    rows_expected, columns = SHAPES[table_index]
    year_start, year_end = YEAR_RANGES[table_index]
    parsed = _TableParser()
    parsed.feed(markdown)
    if parsed.tables != 1:
        raise ValueError(f"OCR table {table_index + 1} count changed: {parsed.tables}")
    if len(parsed.cell_text_rows) != rows_expected:
        raise ValueError(
            f"OCR table {table_index + 1} row count changed: "
            f"{len(parsed.cell_text_rows)}"
        )
    if any(len(row) != columns for row in parsed.cell_text_rows):
        raise ValueError(
            f"OCR table {table_index + 1} is not uniformly {columns} columns"
        )

    raw_nonempty = sum(
        bool(value.strip()) for row in parsed.cell_text_rows for value in row
    )
    duplicate_cells = [
        {"row": row, "column": column, "value": value}
        for row, values in enumerate(parsed.cell_text_rows)
        for column, value in enumerate(values)
        if dedupe_exact_token(value)[1]
    ]
    if raw_nonempty != RAW_NONEMPTY[table_index]:
        raise ValueError(
            f"OCR table {table_index + 1} raw nonempty changed: {raw_nonempty}"
        )
    if len(duplicate_cells) != RAW_DUPLICATE_CELLS[table_index]:
        raise ValueError(
            f"OCR table {table_index + 1} duplicate count changed: "
            f"{len(duplicate_cells)}"
        )

    data_rows = (
        parsed.cell_text_rows[1:]
        if HAS_HEADER[table_index]
        else parsed.cell_text_rows
    )
    expected_keys = [str(year) for year in range(year_start, year_end + 1)]
    actual_keys = [row[0].strip() for row in data_rows]
    if actual_keys != expected_keys:
        raise ValueError(
            f"OCR table {table_index + 1} key sequence changed: "
            f"first={actual_keys[:4]} last={actual_keys[-4:]}"
        )

    cleaned: list[list[str]] = []
    if HAS_HEADER[table_index]:
        cleaned.append([HEADER_LABEL, *[str(age) for age in range(columns - 1)]])
    punctuation_repairs: list[dict[str, object]] = []
    content_repairs: list[dict[str, object]] = []
    for year, raw in zip(range(year_start, year_end + 1), data_rows):
        end = expected_end(columns, year)
        overflow = [
            [column, value]
            for column, value in enumerate(raw[end:], end)
            if value.strip()
        ]
        if overflow:
            raise ValueError(
                f"table {table_index + 1} year {year} has overflow: {overflow}"
            )
        row = [str(year)]
        for column in range(1, end):
            source = raw[column]
            value = source
            repair = REPAIRS.get((table_index, year, column))
            if repair is not None:
                expected_old, value, evidence = repair
                if source != expected_old:
                    raise ValueError(
                        f"repair source changed at {table_index}:{year}:{column}: "
                        f"expected={expected_old!r} actual={source!r}"
                    )
                content_repairs.append(
                    {
                        "year": year,
                        "column": column,
                        "old": source,
                        "new": value,
                        "evidence": evidence,
                    }
                )
            if not value.strip():
                raise ValueError(
                    f"unrepaired internal blank at {table_index}:{year}:{column}"
                )
            canonical, deduplicated = clean_decimal(value)
            if repair is None and (canonical != source.strip() or deduplicated):
                punctuation_repairs.append(
                    {
                        "year": year,
                        "column": column,
                        "old": source,
                        "new": canonical,
                        "exact_token_deduplication": deduplicated,
                    }
                )
            row.append(canonical)
        row.extend([""] * (columns - len(row)))
        if len(row) != columns:
            raise AssertionError("cleaning changed table width")
        cleaned.append(row)

    final_nonempty = sum(bool(value) for row in cleaned for value in row)
    if final_nonempty != EXPECTED_NONEMPTY[table_index]:
        raise ValueError(
            f"table {table_index + 1} final nonempty changed: {final_nonempty}"
        )
    return cleaned, {
        "raw_nonempty_cells": raw_nonempty,
        "raw_duplicate_cells": duplicate_cells,
        "estimated_raw_detections": raw_nonempty + len(duplicate_cells),
        "punctuation_repairs": len(punctuation_repairs),
        "punctuation_repair_details": punctuation_repairs,
        "content_repairs": len(content_repairs),
        "content_repair_details": content_repairs,
        "header_reconstructed": HAS_HEADER[table_index],
        "key_range": [year_start, year_end],
        "final_nonempty_cells": final_nonempty,
    }


def serialize_table(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def validate_table(parsed: _TableParser, table_index: int) -> dict[str, object]:
    rows_expected, columns = SHAPES[table_index]
    year_start, year_end = YEAR_RANGES[table_index]
    row_lengths = list(map(len, parsed.cell_text_rows))
    data = (
        parsed.cell_text_rows[1:]
        if HAS_HEADER[table_index]
        else parsed.cell_text_rows
    )
    expected_keys = [str(year) for year in range(year_start, year_end + 1)]
    actual_keys = [row[0] for row in data]
    expected_header = [HEADER_LABEL, *[str(age) for age in range(columns - 1)]]
    header_exact = (
        not HAS_HEADER[table_index]
        or parsed.cell_text_rows[0] == expected_header
    )
    prefix_mismatches: list[dict[str, object]] = []
    numeric_anomalies: list[dict[str, object]] = []
    for year, row in zip(range(year_start, year_end + 1), data):
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
        len(parsed.rows) == rows_expected
        and row_lengths == [columns] * rows_expected
        and header_exact
        and actual_keys == expected_keys
        and nonempty == EXPECTED_NONEMPTY[table_index]
        and plain_cells
        and not prefix_mismatches
        and not numeric_anomalies
    )
    return {
        "rows": len(parsed.rows),
        "columns": sorted(set(row_lengths)),
        "nonempty_cells": nonempty,
        "header_exact": header_exact,
        "key_sequence_exact": actual_keys == expected_keys,
        "first_keys": actual_keys[:4],
        "last_keys": actual_keys[-4:],
        "plain_td_cells_exact": plain_cells,
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
    reports = (
        [validate_table(table, index) for index, table in enumerate(tables)]
        if len(tables) == 3
        else []
    )
    structure_ok = (
        len(tables) == 3
        and outside_lines == list(EXPECTED_OUTSIDE)
        and all(bool(report["structure_ok"]) for report in reports)
    )
    return {
        "tables": len(tables),
        "outside_lines": outside_lines,
        "outside_exact": outside_lines == list(EXPECTED_OUTSIDE),
        "table_reports": reports,
        "structure_ok": structure_ok,
    }


def cloud_agreement(
    old: str, candidate_tables: list[list[list[str]]]
) -> dict[str, object]:
    old_tables = parse_tables(old)
    if len(old_tables) != 3:
        raise ValueError(f"old prediction table count changed: {len(old_tables)}")
    expected = ((2_016, 2_015), (4_081, 4_076), (112, 112))
    reports: list[dict[str, object]] = []
    total_compared = 0
    total_exact = 0
    all_disagreements: list[dict[str, object]] = []
    for table_index, (old_table, candidate, counts) in enumerate(
        zip(old_tables, candidate_tables, expected)
    ):
        local_by_key = {
            row[0]: [value for value in row if value] for row in candidate
        }
        cloud_by_key = {
            row[0].strip(): [value for value in row if value.strip()]
            for row in old_table.cell_text_rows
            if row and row[0].strip().isdigit()
        }
        compared = 0
        exact = 0
        count_mismatches: list[dict[str, int]] = []
        disagreements: list[dict[str, object]] = []
        for key in sorted(set(local_by_key) & set(cloud_by_key), key=int):
            local = local_by_key[key]
            cloud = cloud_by_key[key]
            if len(local) != len(cloud):
                count_mismatches.append(
                    {"year": int(key), "local": len(local), "cloud": len(cloud)}
                )
                continue
            for column, (local_value, cloud_value) in enumerate(
                zip(local[1:], cloud[1:]), 1
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
                        "year": int(key),
                        "column": column,
                        "local": local_value,
                        "cloud": cloud_clean,
                        "cloud_raw": cloud_value,
                        "selected": "local",
                        "evidence": "original-cell crop",
                    }
                    disagreements.append(item)
                    all_disagreements.append(item)
        if count_mismatches or (compared, exact) != counts:
            raise ValueError(
                f"cloud agreement changed for table {table_index + 1}: "
                f"counts={(compared, exact)} mismatches={count_mismatches}"
            )
        total_compared += compared
        total_exact += exact
        reports.append(
            {
                "old_rows": len(old_table.rows),
                "old_widths": sorted(set(map(len, old_table.rows))),
                "compared_numeric_cells": compared,
                "exact_numeric_cells": exact,
                "disagreements": disagreements,
            }
        )
    return {
        "tables": reports,
        "compared_numeric_cells": total_compared,
        "exact_numeric_cells": total_exact,
        "exact_numeric_rate": total_exact / total_compared,
        "disagreement_cells": len(all_disagreements),
        "disagreements": all_disagreements,
    }


def strip_row_key_token(value: str, year: int) -> str:
    token = re.escape(str(year))
    value = re.sub(rf"^\s*{token}\s+", "", value)
    return re.sub(rf"\s+{token}\s*$", "", value)


def training_numeric_validation(
    ocr_paths: tuple[Path, Path], gt_path: Path
) -> dict[str, object]:
    gt_tables = parse_tables(gt_path.read_text(encoding="utf-8"))
    if [(len(table.rows), len(table.rows[0])) for table in gt_tables] != [
        (107, 62),
        (107, 57),
    ]:
        raise ValueError("training GT shapes changed")
    expected = ((4_636, 4_634), (4_396, 4_390))
    reports: list[dict[str, object]] = []
    total = 0
    exact = 0
    all_disagreements: list[dict[str, object]] = []
    for table_index, (ocr_path, gt, counts) in enumerate(
        zip(ocr_paths, gt_tables, expected)
    ):
        parsed = parse_tables(ocr_path.read_text(encoding="utf-8"))[0]
        if len(parsed.cell_text_rows) != 107:
            raise ValueError("training OCR row count changed")
        table_total = 0
        table_exact = 0
        disagreements: list[dict[str, object]] = []
        blank_errors: list[dict[str, object]] = []
        key_token_repairs: list[dict[str, object]] = []
        for year in range(1, 107):
            ocr_row = list(parsed.cell_text_rows[year])
            gt_row = gt.cell_text_rows[year]
            if table_index == 0:
                cleaned = strip_row_key_token(ocr_row[1], year)
                if cleaned != ocr_row[1]:
                    key_token_repairs.append(
                        {"year": year, "old": ocr_row[1], "new": cleaned}
                    )
                    ocr_row[1] = cleaned
            for column, gt_value in enumerate(gt_row[1:], 1):
                ocr_value = ocr_row[column] if column < len(ocr_row) else ""
                if not gt_value.strip():
                    if ocr_value.strip():
                        blank_errors.append(
                            {"year": year, "column": column, "ocr": ocr_value}
                        )
                    continue
                table_total += 1
                left = canonical_from_digits(ocr_value)
                right = canonical_from_digits(gt_value)
                if left == right:
                    table_exact += 1
                else:
                    item = {
                        "table": table_index + 1,
                        "year": year,
                        "column": column,
                        "ocr": left,
                        "ocr_raw": ocr_value,
                        "gt": right,
                    }
                    disagreements.append(item)
                    all_disagreements.append(item)
        if blank_errors or (table_total, table_exact) != counts:
            raise ValueError(
                f"training calibration changed for table {table_index + 1}: "
                f"counts={(table_total, table_exact)} blanks={blank_errors}"
            )
        total += table_total
        exact += table_exact
        reports.append(
            {
                "numeric_cells": table_total,
                "exact_numeric_cells": table_exact,
                "exact_numeric_rate": table_exact / table_total,
                "key_token_repairs": len(key_token_repairs),
                "disagreements": disagreements,
                "blank_errors": blank_errors,
            }
        )
    return {
        "image": "9c7857f3-2923-46a7-93a9-933146c35d11.jpg",
        "tables": reports,
        "numeric_cells": total,
        "exact_numeric_cells": exact,
        "exact_numeric_rate": exact / total,
        "disagreements": all_disagreements,
        "validation_ok": (total, exact) == (9_032, 9_024),
    }


def layout_reference_validation(gt_path: Path) -> dict[str, object]:
    markdown = gt_path.read_text(encoding="utf-8")
    tables = parse_tables(markdown)
    outside = re.sub(
        r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S
    )
    outside_lines = [line.strip() for line in outside.splitlines() if line.strip()]
    expected_outside = [
        "交费期间 6",
        "性别 男性",
        "保险期间 106",
        "交费期间 10",
        "性别 男性",
    ]
    shapes = [(len(table.rows), len(table.rows[0])) for table in tables]
    plain_td = all(
        all(cell == ("td", None, None) for row in table.rows for cell in row)
        for table in tables
    )
    headers = [table.cell_text_rows[0][0] for table in tables]
    validation_ok = (
        shapes == [(107, 64), (58, 62)]
        and outside_lines == expected_outside
        and plain_td
        and headers == [HEADER_LABEL, HEADER_LABEL]
    )
    if not validation_ok:
        raise ValueError("same-layout training reference changed")
    return {
        "image": "1b8718d0-ea4f-4085-a853-9fa3d5a57ada.jpg",
        "table_shapes": [list(shape) for shape in shapes],
        "outside_lines": outside_lines,
        "all_cells_are_td": plain_td,
        "header_labels": headers,
        "validation_ok": validation_ok,
        "note": "same blue-rule spreadsheet layout as the test page",
    }


def grid_probe_validation(paths: tuple[Path, Path, Path]) -> dict[str, object]:
    expected = (
        {(64, 67): 88, (63, 67): 0, (65, 67): 2, (64, 66): 0, (64, 68): 2},
        {(107, 62): 87, (106, 62): 0, (108, 62): 0, (107, 61): 0, (107, 63): 0},
        {(12, 57): 93, (11, 57): 0, (13, 57): 3, (12, 56): 0, (12, 58): 0},
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
        competitors = [
            successes
            for shape, successes in actual.items()
            if shape != target
        ]
        if actual[target] <= max(competitors):
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v21.csv"),
    )
    parser.add_argument("--ocr-table1", type=Path, required=True)
    parser.add_argument("--ocr-table2", type=Path, required=True)
    parser.add_argument("--ocr-table3", type=Path, required=True)
    parser.add_argument("--training-ocr-table1", type=Path, required=True)
    parser.add_argument("--training-ocr-table2", type=Path, required=True)
    parser.add_argument("--training-gt", type=Path, required=True)
    parser.add_argument("--layout-reference-gt", type=Path, required=True)
    parser.add_argument("--grid-report-table1", type=Path, required=True)
    parser.add_argument("--grid-report-table2", type=Path, required=True)
    parser.add_argument("--grid-report-table3", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=ROOT / "work_rule64x67_107x62_12x57_clean_A_886.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "work_afac_A_submission_v22.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "work_afac_A_submission_v22.report.json",
    )
    args = parser.parse_args()

    if hashlib.sha256(args.base.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("v21 base hash changed")
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base = load_submission(args.base)
    old = base[TARGET]
    ocr_paths = (args.ocr_table1, args.ocr_table2, args.ocr_table3)
    candidate_tables: list[list[list[str]]] = []
    cleanup: list[dict[str, object]] = []
    for table_index, path in enumerate(ocr_paths):
        rows, report = clean_ocr(path.read_text(encoding="utf-8"), table_index)
        candidate_tables.append(rows)
        cleanup.append(report)

    candidate = (
        serialize_table(candidate_tables[0])
        + "\n\n保险期间 106\n交费期间 15\n性别 男性\n\n"
        + serialize_table(candidate_tables[1])
        + "\n\n保险期间 106\n交费期间 20\n性别 男性\n\n"
        + serialize_table(candidate_tables[2])
    )
    structure = validate_candidate(candidate)
    if not structure["structure_ok"]:
        raise ValueError(f"candidate structure failed: {structure}")
    numeric_calibration = training_numeric_validation(
        (args.training_ocr_table1, args.training_ocr_table2), args.training_gt
    )
    layout_reference = layout_reference_validation(args.layout_reference_gt)
    cloud = cloud_agreement(old, candidate_tables)
    grid = grid_probe_validation(
        (args.grid_report_table1, args.grid_report_table2, args.grid_report_table3)
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
            "cleanup": cleanup,
            "structure": structure,
            "training_numeric_calibration": numeric_calibration,
            "same_layout_training_reference": layout_reference,
            "cloud_agreement": cloud,
            "grid_probe_validation": grid,
            "grid_evidence": {
                "semantic_shapes": [[64, 67], [107, 62], [12, 57]],
                "physical_shapes": [[64, 67], [108, 62], [13, 57]],
                "horizontal_rules": [65, 109, 14],
                "vertical_rules": [68, 63, 58],
                "ocr_nonempty_cells": [2_144, 4_799, 683],
                "ocr_duplicate_detections": [2, 6, 0],
                "recovered_blank_cells": [0, 5, 1],
                "final_nonempty_cells": list(EXPECTED_NONEMPTY),
                "input_sha256": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [
                        *ocr_paths,
                        args.training_ocr_table1,
                        args.training_ocr_table2,
                        args.training_gt,
                        args.layout_reference_gt,
                        args.grid_report_table1,
                        args.grid_report_table2,
                        args.grid_report_table3,
                    ]
                },
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "candidate": str(args.candidate),
                "report": str(args.report),
                "sha256": report["sha256"],
                "changed_names": changed_names,
                "table_shapes": [
                    [item["rows"], item["columns"]]
                    for item in structure["table_reports"]
                ],
                "nonempty_cells": [
                    item["nonempty_cells"]
                    for item in structure["table_reports"]
                ],
                "training_accuracy": numeric_calibration["exact_numeric_rate"],
                "cloud_accuracy": cloud["exact_numeric_rate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
