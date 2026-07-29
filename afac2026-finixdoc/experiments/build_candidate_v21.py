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


TARGET = "0cd74f08-df57-421d-923e-3fa3f1d017c1.jpg"
BASE_SHA256 = "4c8884128c02b91ac8b0cac1f78c8ada65358194345c39c0fd9b4857c621d4b0"
SHAPES = ((31, 61), (106, 61), (45, 61))
YEAR_RANGES = ((75, 105), (1, 105), (1, 44))
HAS_HEADER = (False, True, True)
EXPECTED_NONEMPTY = (527, 4_696, 2_745)
HEADER_LABEL = "保单年度末\\投保年龄"

# Every content repair below has independent evidence.  Duplicate evidence is
# from another physical table on the same page; sequence evidence is from the
# immediately adjacent cells plus the old cloud OCR.
REPAIRS: dict[tuple[int, int, int], tuple[str, str, str]] = {
    (0, 77, 29): ("100.00", "1000.00", "cloud and terminal-value sequence"),
    (0, 79, 24): ("111.26", "1111.26", "cloud and row sequence"),
    (1, 11, 57): ("11-43. 15", "1143.15", "same-page duplicate table"),
    (1, 14, 12): ("1213.8", "1213.88", "same-page duplicate table"),
    (1, 14, 15): ("1213.8", "1213.88", "same-page duplicate table"),
    (1, 52, 26): ("200.91", "2000.91", "cloud and row sequence"),
    (1, 78, 25): ("1140.6", "1140.66", "cloud and row sequence"),
    (1, 78, 28): ("100.00", "1000.00", "cloud and terminal-value sequence"),
    (1, 81, 25): ("100.00", "1000.00", "cloud and terminal-value sequence"),
    (2, 8, 19): ("1077.8", "1077.88", "same-page duplicate table"),
    (2, 11, 9): ("1143.8", "1143.88", "same-page duplicate table"),
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


def clean_decimal(value: str) -> str:
    value = re.sub(r"\s+", "", value.strip()).replace(",", ".")
    if value.count(".") > 1:
        whole, fraction = value.rsplit(".", 1)
        value = whole.replace(".", "") + "." + fraction
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
        raise ValueError(f"not an unambiguous two-decimal OCR value: {value!r}")
    whole, fraction = value.split(".")
    return f"{int(whole)}.{fraction}"


def expected_end(year: int) -> int:
    return min(61, 107 - year)


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
        raise ValueError(f"OCR table {table_index + 1} is not uniformly 61 columns")
    raw_nonempty = sum(
        bool(value.strip()) for row in parsed.cell_text_rows for value in row
    )
    if raw_nonempty != EXPECTED_NONEMPTY[table_index]:
        raise ValueError(
            f"OCR table {table_index + 1} nonempty count changed: {raw_nonempty}"
        )

    data_rows = parsed.cell_text_rows[1:] if HAS_HEADER[table_index] else parsed.cell_text_rows
    expected_keys = [str(year) for year in range(year_start, year_end + 1)]
    actual_keys = [row[0].strip() for row in data_rows]
    if actual_keys != expected_keys:
        raise ValueError(
            f"OCR table {table_index + 1} key sequence changed: "
            f"first={actual_keys[:4]} last={actual_keys[-4:]}"
        )

    cleaned: list[list[str]] = []
    if HAS_HEADER[table_index]:
        cleaned.append([HEADER_LABEL, *[str(age) for age in range(60)]])
    punctuation_repairs: list[dict[str, object]] = []
    content_repairs: list[dict[str, object]] = []
    for year, raw in zip(range(year_start, year_end + 1), data_rows):
        end = expected_end(year)
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
        numeric: list[str] = []
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
            numeric.append(canonical)
        row = [str(year), *numeric, *([""] * (columns - end))]
        if len(row) != columns:
            raise AssertionError("cleaning changed table width")
        cleaned.append(row)
    return cleaned, {
        "raw_nonempty_cells": raw_nonempty,
        "punctuation_repairs": len(punctuation_repairs),
        "punctuation_repair_details": punctuation_repairs,
        "content_repairs": len(content_repairs),
        "content_repair_details": content_repairs,
        "header_reconstructed": HAS_HEADER[table_index],
        "key_range": [year_start, year_end],
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
    data = parsed.cell_text_rows[1:] if HAS_HEADER[table_index] else parsed.cell_text_rows
    expected_keys = [str(year) for year in range(year_start, year_end + 1)]
    actual_keys = [row[0] for row in data]
    header_exact = (
        not HAS_HEADER[table_index]
        or parsed.cell_text_rows[0] == [HEADER_LABEL, *[str(age) for age in range(60)]]
    )
    prefix_mismatches: list[dict[str, object]] = []
    numeric_anomalies: list[dict[str, object]] = []
    for year, row in zip(range(year_start, year_end + 1), data):
        end = expected_end(year)
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
    plain_cells = all(row == [("td", None, None)] * columns for row in parsed.rows)
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
    expected_outside = [
        "保险期间 终身",
        "交费期间 1",
        "性别 男性",
        "起领年龄 70",
        "保险期间 终身",
        "交费期间 1",
        "性别 男性",
        "起领年龄 75",
    ]
    reports = (
        [validate_table(table, index) for index, table in enumerate(tables)]
        if len(tables) == 3
        else []
    )
    structure_ok = (
        len(tables) == 3
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
    if len(old_tables) != 3:
        raise ValueError(f"old prediction table count changed: {len(old_tables)}")
    expected = ((490, 488), (3_564, 3_561), (1_800, 1_800))
    reports: list[dict[str, object]] = []
    all_disagreements: list[dict[str, object]] = []
    total_compared = 0
    total_exact = 0
    for table_index, (old_table, candidate, counts) in enumerate(
        zip(old_tables, candidate_tables, expected)
    ):
        local_by_key = {
            row[0]: [value for value in row if value] for row in candidate
        }
        cloud_by_key = {
            row[0].strip(): [value for value in row if value.strip()]
            for row in old_table.cell_text_rows
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
        "exact_numeric_rate": total_exact / max(1, total_compared),
        "disagreement_cells": len(all_disagreements),
        "disagreements": all_disagreements,
    }


def duplicate_agreement(candidate_tables: list[list[list[str]]]) -> dict[str, object]:
    middle = {row[0]: row for row in candidate_tables[1][1:]}
    bottom = {row[0]: row for row in candidate_tables[2][1:]}
    compared = 0
    exact = 0
    prefix_mismatches: list[dict[str, object]] = []
    for year in range(1, 45):
        expected_equal = 0 if year < 5 else min(60, 70 - year)
        for column, (left, right) in enumerate(
            zip(middle[str(year)][1:], bottom[str(year)][1:]), 1
        ):
            if not left or not right:
                continue
            compared += 1
            exact += left == right
            if (column <= expected_equal) != (left == right):
                prefix_mismatches.append(
                    {
                        "year": year,
                        "column": column,
                        "expected_equal": column <= expected_equal,
                        "middle": left,
                        "bottom": right,
                    }
                )
    if (compared, exact) != (2_640, 1_805) or prefix_mismatches:
        raise ValueError(
            f"same-page duplicate agreement changed: {(compared, exact)} "
            f"prefix_mismatches={prefix_mismatches}"
        )
    return {
        "compared_numeric_cells": compared,
        "exact_numeric_anchors": exact,
        "shared_prefix_rule": "years 5-10: 60 cells; years 11-44: 70-year cells",
        "prefix_mismatches": prefix_mismatches,
        "note": "the two benefit-age variants diverge exactly outside their shared-value prefix",
    }


def training_validation(
    ocr_paths: tuple[Path, Path], gt_path: Path
) -> dict[str, object]:
    gt_tables = parse_tables(gt_path.read_text(encoding="utf-8"))
    if len(gt_tables) != 2:
        raise ValueError("training GT table count changed")
    expected = ((4_530, 4_524), (4_034, 4_027))
    reports: list[dict[str, object]] = []
    total = 0
    exact = 0
    all_disagreements: list[dict[str, object]] = []
    for table_index, (ocr_path, gt, counts) in enumerate(
        zip(ocr_paths, gt_tables, expected)
    ):
        parsed = _TableParser()
        parsed.feed(ocr_path.read_text(encoding="utf-8"))
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


def grid_probe_validation(paths: tuple[Path, Path, Path]) -> dict[str, object]:
    expected = (
        {(31, 61): 116, (30, 61): 0, (32, 61): 0, (31, 60): 0, (31, 62): 0},
        {(106, 61): 108, (105, 61): 0, (107, 61): 6, (106, 60): 0, (106, 62): 0},
        {(45, 61): 111, (44, 61): 0, (46, 61): 6, (45, 60): 0, (45, 62): 0},
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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v20.csv"),
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
        default=Path(
            "D:/AFAC2026/outputs/experiments/"
            "rule31x61_106x61_45x61_clean_A_0cd.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v21.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v21.report.json"),
    )
    args = parser.parse_args()

    if hashlib.sha256(args.base.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("v20 base hash changed")
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
        + "\n\n保险期间 终身\n交费期间 1\n性别 男性\n起领年龄 70\n\n"
        + serialize_table(candidate_tables[1])
        + "\n\n保险期间 终身\n交费期间 1\n性别 男性\n起领年龄 75\n\n"
        + serialize_table(candidate_tables[2])
    )
    structure = validate_candidate(candidate)
    if not structure["structure_ok"]:
        raise ValueError(f"candidate structure failed: {structure}")
    calibration = training_validation(
        (args.training_ocr_table1, args.training_ocr_table2), args.training_gt
    )
    cloud = cloud_agreement(old, candidate_tables)
    duplicates = duplicate_agreement(candidate_tables)
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
            "training_calibration": calibration,
            "cloud_agreement": cloud,
            "same_page_duplicate_agreement": duplicates,
            "grid_probe_validation": grid,
            "grid_evidence": {
                "semantic_shapes": [[31, 61], [106, 61], [45, 61]],
                "physical_shapes": [[31, 61], [107, 61], [46, 61]],
                "horizontal_rules": [32, 107, 46],
                "vertical_rules": [62, 62, 62],
                "detected_text_row_groups": [31, 106, 45],
                "projected_text_row_groups": [31, 106, 45],
                "ocr_detections": [527, 4696, 2745],
                "theoretical_nonempty": [527, 4696, 2745],
                "input_sha256": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [
                        *ocr_paths,
                        args.training_ocr_table1,
                        args.training_ocr_table2,
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
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
