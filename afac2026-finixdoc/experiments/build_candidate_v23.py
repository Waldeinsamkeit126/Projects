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


TARGET = "3b243a83-1024-4139-b39c-a987cdeece47.jpg"
BASE_SHA256 = "2ee4389452cf0e8cca19beb451bc8bfd2edb4ab15d855f0e068a5577b716c4f7"
SHAPES = ((61, 61), (46, 27), (75, 61))
YEAR_RANGES = ((45, 105), (1, 45), (1, 74))
HAS_HEADER = (False, True, True)
EXPECTED_NONEMPTY = (1_951, 917, 4_169)
HEADER_LABEL = "保单年度末\\投保年龄"
EXPECTED_OUTSIDE = (
    "保险期间 终身",
    "交费期间 1",
    "性别 男性",
    "起领年龄 首个保单周年日起领",
    "保险期间 终身",
    "交费期间 3",
    "性别 男性",
    "起领年龄 60",
)

# Each repair is directly readable in a rule-grid-addressed enlarged crop of
# the source image and is independently supported by the old cloud OCR.
REPAIRS: dict[tuple[int, int, int], tuple[str, str, str]] = {
    (0, 54, 31): ("1889.01", "1889.04", "original-cell crop and cloud OCR"),
    (0, 76, 30): ("100.00", "1000.00", "original-cell crop and cloud OCR"),
    (1, 22, 24): ("100.00", "1000.00", "original-cell crop and cloud OCR"),
    (1, 39, 3): ("986.8", "986.88", "original-cell crop and cloud OCR"),
    (2, 65, 9): ("6425.8", "6425.88", "original-cell crop and cloud OCR"),
    (2, 73, 33): ("300.00", "3000.00", "original-cell crop and cloud OCR"),
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
    parsed: list[_TableParser] = []
    for match in re.findall(
        r"<table[^>]*>.*?</table>", markdown, flags=re.I | re.S
    ):
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


def clean_decimal(value: str) -> str:
    value = re.sub(r"\s+", "", value.strip()).replace(",", ".").replace("-", "")
    if value.count(".") > 1:
        whole, fraction = value.rsplit(".", 1)
        value = whole.replace(".", "") + "." + fraction
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
        raise ValueError(f"not an unambiguous two-decimal OCR value: {value!r}")
    whole, fraction = value.split(".")
    return f"{int(whole)}.{fraction}"


def expected_end(table_index: int, columns: int, year: int) -> int:
    if table_index == 1:
        return min(columns, 47 - year)
    return min(columns, 107 - year)


def header_for(table_index: int) -> list[str]:
    if table_index == 1:
        return [HEADER_LABEL, *[str(age) for age in range(60, 86)]]
    if table_index == 2:
        return [HEADER_LABEL, *[str(age) for age in range(60)]]
    raise ValueError("continuation table has no header")


def clean_ocr(
    markdown: str, table_index: int
) -> tuple[list[list[str]], dict[str, object]]:
    rows_expected, columns = SHAPES[table_index]
    year_start, year_end = YEAR_RANGES[table_index]
    parsed = _TableParser()
    parsed.feed(markdown)
    if parsed.tables != 1:
        raise ValueError(f"OCR table {table_index + 1} count changed")
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
    if raw_nonempty != EXPECTED_NONEMPTY[table_index]:
        raise ValueError(
            f"OCR table {table_index + 1} nonempty changed: {raw_nonempty}"
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
        cleaned.append(header_for(table_index))
    punctuation_repairs: list[dict[str, object]] = []
    content_repairs: list[dict[str, object]] = []
    for year, raw in zip(range(year_start, year_end + 1), data_rows):
        end = expected_end(table_index, columns, year)
        internal = [column for column, value in enumerate(raw[:end]) if not value.strip()]
        overflow = [
            [column, value]
            for column, value in enumerate(raw[end:], end)
            if value.strip()
        ]
        if internal or overflow:
            raise ValueError(
                f"table {table_index + 1} year {year} violates prefix: "
                f"internal={internal} overflow={overflow}"
            )
        row = [str(year)]
        for column, source in enumerate(raw[1:end], 1):
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
            canonical = clean_decimal(value)
            if repair is None and canonical != source.strip():
                punctuation_repairs.append(
                    {
                        "year": year,
                        "column": column,
                        "old": source,
                        "new": canonical,
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
    data = (
        parsed.cell_text_rows[1:]
        if HAS_HEADER[table_index]
        else parsed.cell_text_rows
    )
    expected_keys = [str(year) for year in range(year_start, year_end + 1)]
    actual_keys = [row[0] for row in data]
    header_exact = (
        not HAS_HEADER[table_index]
        or parsed.cell_text_rows[0] == header_for(table_index)
    )
    prefix_mismatches: list[dict[str, object]] = []
    numeric_anomalies: list[dict[str, object]] = []
    for year, row in zip(range(year_start, year_end + 1), data):
        end = expected_end(table_index, columns, year)
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
    row_lengths = list(map(len, parsed.cell_text_rows))
    nonempty = sum(
        bool(value.strip()) for row in parsed.cell_text_rows for value in row
    )
    plain_td = all(
        row == [("td", None, None)] * columns for row in parsed.rows
    )
    structure_ok = (
        len(parsed.rows) == rows_expected
        and row_lengths == [columns] * rows_expected
        and header_exact
        and actual_keys == expected_keys
        and nonempty == EXPECTED_NONEMPTY[table_index]
        and plain_td
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
        "plain_td_cells_exact": plain_td,
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
    expected = ((1_590, 1_583), (685, 683), (3_794, 3_793))
    expected_count_mismatches = ([], [[31, 16, 10]], [])
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
        count_mismatches: list[list[int]] = []
        disagreements: list[dict[str, object]] = []
        for key in sorted(set(local_by_key) & set(cloud_by_key), key=int):
            local = local_by_key[key]
            cloud = cloud_by_key[key]
            if len(local) != len(cloud):
                count_mismatches.append([int(key), len(local), len(cloud)])
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
                        "evidence": "original-cell crop or cloud digit truncation",
                    }
                    disagreements.append(item)
                    all_disagreements.append(item)
        if (
            count_mismatches != expected_count_mismatches[table_index]
            or (compared, exact) != counts
        ):
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
                "count_mismatches": count_mismatches,
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


def training_validation(
    ocr_paths: tuple[Path, Path], gt_path: Path
) -> dict[str, object]:
    gt_tables = parse_tables(gt_path.read_text(encoding="utf-8"))
    expected_shapes = [(106, 61), (75, 61)]
    actual_shapes = [(len(table.rows), len(table.rows[0])) for table in gt_tables]
    if actual_shapes != expected_shapes:
        raise ValueError(f"training GT shapes changed: {actual_shapes}")
    expected = ((4_530, 4_524), (4_034, 4_027))
    reports: list[dict[str, object]] = []
    total = 0
    exact = 0
    all_disagreements: list[dict[str, object]] = []
    for table_index, (ocr_path, gt, counts) in enumerate(
        zip(ocr_paths, gt_tables, expected)
    ):
        parsed = parse_tables(ocr_path.read_text(encoding="utf-8"))[0]
        if len(parsed.cell_text_rows) != len(gt.cell_text_rows):
            raise ValueError("training OCR row count changed")
        table_total = 0
        table_exact = 0
        disagreements: list[dict[str, object]] = []
        blank_errors: list[dict[str, object]] = []
        for row_index, (ocr_row, gt_row) in enumerate(
            zip(parsed.cell_text_rows[1:], gt.cell_text_rows[1:]), 1
        ):
            for column, (ocr_value, gt_value) in enumerate(
                zip(ocr_row[1:], gt_row[1:]), 1
            ):
                if not gt_value.strip():
                    if ocr_value.strip():
                        blank_errors.append(
                            {"row": row_index, "column": column, "ocr": ocr_value}
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
                        "row": row_index,
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
                "disagreements": disagreements,
                "blank_errors": blank_errors,
            }
        )
    return {
        "image": "734ca707-dfb3-41e5-8183-74c9cc37281c.jpg",
        "tables": reports,
        "numeric_cells": total,
        "exact_numeric_cells": exact,
        "exact_numeric_rate": exact / total,
        "disagreements": all_disagreements,
        "validation_ok": (total, exact) == (8_564, 8_551),
    }


def layout_reference_validation(gt_path: Path) -> dict[str, object]:
    markdown = gt_path.read_text(encoding="utf-8")
    tables = parse_tables(markdown)
    shapes = [(len(table.rows), len(table.rows[0])) for table in tables]
    plain_td = all(
        all(cell == ("td", None, None) for row in table.rows for cell in row)
        for table in tables
    )
    headers = [table.cell_text_rows[0][0] for table in tables]
    outside = re.sub(
        r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S
    )
    outside_lines = [line.strip() for line in outside.splitlines() if line.strip()]
    metadata_tail = outside_lines[-8:]
    expected_tail = [
        "保险期间 终身",
        "交费期间 1",
        "性别 男性",
        "起领年龄 60",
        "保险期间 终身",
        "交费期间 1",
        "性别 男性",
        "起领年龄 65",
    ]
    validation_ok = (
        shapes == [(106, 61), (75, 61)]
        and plain_td
        and headers == [HEADER_LABEL, HEADER_LABEL]
        and metadata_tail == expected_tail
    )
    if not validation_ok:
        raise ValueError("same-layout training reference changed")
    return {
        "image": "734ca707-dfb3-41e5-8183-74c9cc37281c.jpg",
        "table_shapes": [list(shape) for shape in shapes],
        "metadata_tail": metadata_tail,
        "all_cells_are_td": plain_td,
        "header_labels": headers,
        "validation_ok": validation_ok,
    }


def grid_probe_validation(paths: tuple[Path, Path, Path]) -> dict[str, object]:
    expected = (
        {(61, 61): 114, (60, 61): 0, (62, 61): 0, (61, 60): 0, (61, 62): 0},
        {(46, 27): 120, (45, 27): 0, (47, 27): 0, (46, 26): 0, (46, 28): 0},
        {(75, 61): 108, (74, 61): 0, (76, 61): 0, (75, 60): 0, (75, 62): 0},
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v22.csv"),
    )
    parser.add_argument("--ocr-table1", type=Path, required=True)
    parser.add_argument("--ocr-table2", type=Path, required=True)
    parser.add_argument("--ocr-table3", type=Path, required=True)
    parser.add_argument("--training-ocr-table1", type=Path, required=True)
    parser.add_argument("--training-ocr-table2", type=Path, required=True)
    parser.add_argument("--training-gt", type=Path, required=True)
    parser.add_argument("--grid-report-table1", type=Path, required=True)
    parser.add_argument("--grid-report-table2", type=Path, required=True)
    parser.add_argument("--grid-report-table3", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=ROOT / "work_rule61x61_46x27_75x61_clean_A_3b243.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "work_afac_A_submission_v23.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "work_afac_A_submission_v23.report.json",
    )
    args = parser.parse_args()

    if hashlib.sha256(args.base.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("v22 base hash changed")
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
        + "\n\n保险期间 终身\n交费期间 1\n性别 男性\n起领年龄 首个保单周年日起领\n\n"
        + serialize_table(candidate_tables[1])
        + "\n\n保险期间 终身\n交费期间 3\n性别 男性\n起领年龄 60\n\n"
        + serialize_table(candidate_tables[2])
    )
    structure = validate_candidate(candidate)
    if not structure["structure_ok"]:
        raise ValueError(f"candidate structure failed: {structure}")
    training = training_validation(
        (args.training_ocr_table1, args.training_ocr_table2), args.training_gt
    )
    layout = layout_reference_validation(args.training_gt)
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
            "training_calibration": training,
            "same_layout_training_reference": layout,
            "cloud_agreement": cloud,
            "grid_probe_validation": grid,
            "grid_evidence": {
                "semantic_shapes": [[61, 61], [46, 27], [75, 61]],
                "physical_shapes": [[61, 61], [47, 27], [76, 61]],
                "excluded_spanning_title_rows": [0, 1, 1],
                "semantic_horizontal_rules": [62, 47, 76],
                "vertical_rules": [62, 28, 62],
                "ocr_detections": list(EXPECTED_NONEMPTY),
                "theoretical_nonempty": list(EXPECTED_NONEMPTY),
                "input_sha256": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [
                        *ocr_paths,
                        args.training_ocr_table1,
                        args.training_ocr_table2,
                        args.training_gt,
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
                "training_accuracy": training["exact_numeric_rate"],
                "cloud_accuracy": cloud["exact_numeric_rate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
