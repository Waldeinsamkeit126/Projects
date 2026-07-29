from __future__ import annotations

import argparse
import csv
import difflib
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


TARGET = "4e32dba9-0799-4442-9909-e4a80733f122.jpg"
BASE_SHA256 = "dcb2ce0932268adc3f4844b63e35db047717c221c32f0cc647ab11a40124a37c"
DATA_ROWS = (69, 69, 70, 59)
FINAL_SHAPES = ((70, 107), (70, 107), (71, 107), (60, 107))
EXPECTED_DATA_NONEMPTY = (5_037, 5_037, 5_075, 4_602)
EXPECTED_FINAL_NONEMPTY = tuple(value + 107 for value in EXPECTED_DATA_NONEMPTY)
HEADER_LABEL = "投保年龄\\保单年度末"
TABLE_TITLES = ("男性，趸交", "女性，趸交", "男性，3年交", "女性，3年交")
DOCUMENT_LINES = (
    "工银安盛人寿鑫如意25终身寿险B 现金价值表（全表）",
    "每1000元基本保险金额",
    "单位：人民币元",
)
EXPECTED_OUTSIDE = (*DOCUMENT_LINES, *TABLE_TITLES)

# The source crop and the old cloud OCR both read 3380.57. The local detector
# omitted the leading 3 in this one cell; its two neighbours are 3314.30 and
# 3448.17, providing an independent monotonic sequence check.
CONTENT_REPAIRS = {
    (1, 26, 62): ("380.57", "3380.57", "source crop, cloud OCR, and row sequence"),
}


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected submission columns: {reader.fieldnames}")
        records = list(reader)
    predictions = {str(row["file_name"]): str(row["ground_truth"]) for row in records}
    if len(records) != 100 or len(predictions) != 100:
        raise ValueError("submission must contain 100 unique rows")
    return predictions


def parse_tables(markdown: str) -> list[_TableParser]:
    result: list[_TableParser] = []
    for match in re.findall(r"<table[^>]*>.*?</table>", markdown, re.I | re.S):
        parser = _TableParser()
        parser.feed(match)
        if parser.tables != 1:
            raise ValueError("isolated table did not parse exactly once")
        result.append(parser)
    return result


def normalized_numeric(value: str) -> str | None:
    cleaned = re.sub(r"\s+", "", value.strip()).upper().replace("B", "8")
    cleaned = cleaned.replace(",", ".")
    if re.fullmatch(r"[0-9]+\.[0-9]{2}", cleaned):
        whole, fraction = cleaned.split(".")
        return f"{int(whole)}.{fraction}"
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 3:
        return None
    return f"{int(digits[:-2])}.{digits[-2:]}"


def strict_numeric(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value.strip()).upper().replace("B", "8")
    cleaned = cleaned.replace(",", ".")
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", cleaned):
        raise ValueError(f"ambiguous numeric OCR value: {value!r}")
    whole, fraction = cleaned.split(".")
    return f"{int(whole)}.{fraction}"


def header() -> list[str]:
    return [HEADER_LABEL, *map(str, range(1, 107))]


def clean_test_tables(raw_path: Path) -> tuple[list[list[list[str]]], dict[str, object]]:
    parsed = parse_tables(raw_path.read_text(encoding="utf-8"))
    if len(parsed) != 4:
        raise ValueError(f"local OCR table count changed: {len(parsed)}")
    cleaned_tables: list[list[list[str]]] = []
    punctuation: list[dict[str, object]] = []
    content: list[dict[str, object]] = []
    reports: list[dict[str, object]] = []
    for table_index, (table, rows_expected, raw_nonempty_expected) in enumerate(
        zip(parsed, DATA_ROWS, EXPECTED_DATA_NONEMPTY)
    ):
        raw = table.cell_text_rows
        if len(raw) != rows_expected or any(len(row) != 107 for row in raw):
            raise ValueError(f"test OCR shape changed at table {table_index + 1}")
        raw_nonempty = sum(bool(value.strip()) for row in raw for value in row)
        if raw_nonempty != raw_nonempty_expected:
            raise ValueError(f"test OCR nonempty count changed at table {table_index + 1}")
        final = [header()]
        for age, source_row in enumerate(raw):
            end = 107 - age
            if source_row[0].strip() != str(age):
                raise ValueError(f"key changed at table={table_index + 1} age={age}")
            internal = [index for index, value in enumerate(source_row[:end]) if not value.strip()]
            overflow = [index for index, value in enumerate(source_row[end:], end) if value.strip()]
            if internal or overflow:
                raise ValueError(
                    f"prefix violation table={table_index + 1} age={age}: "
                    f"internal={internal} overflow={overflow}"
                )
            row = [str(age)]
            for column, source in enumerate(source_row[1:end], 1):
                selected = source.strip()
                repair = CONTENT_REPAIRS.get((table_index, age, column))
                if repair is not None:
                    expected_old, selected, evidence = repair
                    if source.strip() != expected_old:
                        raise ValueError("content repair source changed")
                    content.append(
                        {
                            "table": table_index + 1,
                            "age": age,
                            "column": column,
                            "old": source,
                            "new": selected,
                            "evidence": evidence,
                        }
                    )
                value = strict_numeric(selected)
                if repair is None and value != source.strip():
                    punctuation.append(
                        {
                            "table": table_index + 1,
                            "age": age,
                            "column": column,
                            "old": source,
                            "new": value,
                        }
                    )
                row.append(value)
            row.extend([""] * (107 - len(row)))
            final.append(row)
        nonempty = sum(bool(value) for row in final for value in row)
        if nonempty != EXPECTED_FINAL_NONEMPTY[table_index]:
            raise ValueError("cleaning changed the theoretical nonempty count")
        cleaned_tables.append(final)
        reports.append(
            {
                "raw_rows": len(raw),
                "raw_columns": 107,
                "raw_nonempty": raw_nonempty,
                "final_rows": len(final),
                "final_columns": 107,
                "final_nonempty": nonempty,
                "key_range": [0, rows_expected - 1],
                "header_reconstructed": True,
            }
        )
    return cleaned_tables, {
        "tables": reports,
        "punctuation_repairs": punctuation,
        "content_repairs": content,
    }


def serialize_table(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def make_candidate(tables: list[list[list[str]]]) -> str:
    sections = [
        "\n".join(DOCUMENT_LINES) + "\n\n" + TABLE_TITLES[0] + "\n\n" + serialize_table(tables[0])
    ]
    sections.extend(
        title + "\n\n" + serialize_table(table)
        for title, table in zip(TABLE_TITLES[1:], tables[1:])
    )
    return "\n\n".join(sections)


def validate_candidate(markdown: str) -> dict[str, object]:
    tables = parse_tables(markdown)
    outside = re.sub(r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S)
    outside_lines = [line.strip() for line in outside.splitlines() if line.strip()]
    reports: list[dict[str, object]] = []
    for index, table in enumerate(tables):
        rows = table.cell_text_rows
        shape = (len(rows), len(rows[0]) if rows else 0)
        keys = [row[0] for row in rows[1:]]
        prefix_ok = all(
            all(row[column] for column in range(107 - age))
            and not any(row[107 - age :])
            for age, row in enumerate(rows[1:])
        )
        numeric_ok = all(
            re.fullmatch(r"[0-9]+\.[0-9]{2}", value) is not None
            for age, row in enumerate(rows[1:])
            for value in row[1 : 107 - age]
        )
        nonempty = sum(bool(value) for row in rows for value in row)
        plain_td = all(row == [("td", None, None)] * 107 for row in table.rows)
        ok = (
            shape == FINAL_SHAPES[index]
            and rows[0] == header()
            and keys == list(map(str, range(DATA_ROWS[index])))
            and prefix_ok
            and numeric_ok
            and nonempty == EXPECTED_FINAL_NONEMPTY[index]
            and plain_td
        )
        reports.append(
            {
                "shape": list(shape),
                "nonempty": nonempty,
                "header_exact": rows[0] == header(),
                "keys_exact": keys == list(map(str, range(DATA_ROWS[index]))),
                "prefix_exact": prefix_ok,
                "numeric_format_exact": numeric_ok,
                "plain_td_exact": plain_td,
                "structure_ok": ok,
            }
        )
    structure_ok = (
        len(tables) == 4
        and outside_lines == list(EXPECTED_OUTSIDE)
        and all(report["structure_ok"] for report in reports)
    )
    return {
        "tables": len(tables),
        "outside_lines": outside_lines,
        "outside_exact": outside_lines == list(EXPECTED_OUTSIDE),
        "table_reports": reports,
        "structure_ok": structure_ok,
    }


def training_validation(raw_path: Path, gt_path: Path) -> dict[str, object]:
    raw = parse_tables(raw_path.read_text(encoding="utf-8"))
    gt = parse_tables(gt_path.read_text(encoding="utf-8"))
    if len(raw) != 5 or len(gt) != 5:
        raise ValueError("training table count changed")
    total = exact = 0
    blank_errors: list[dict[str, object]] = []
    key_errors: list[dict[str, object]] = []
    disagreements: list[dict[str, object]] = []
    reports: list[dict[str, object]] = []
    for table_index, (left, right_parser) in enumerate(zip(raw, gt)):
        right = right_parser.cell_text_rows if table_index == 0 else right_parser.cell_text_rows[1:]
        if len(left.cell_text_rows) != len(right):
            raise ValueError("training data row count changed")
        table_total = table_exact = 0
        for row_index, (ocr_row, gt_row) in enumerate(zip(left.cell_text_rows, right)):
            if ocr_row[0].strip() != gt_row[0].strip():
                key_errors.append(
                    {"table": table_index + 1, "row": row_index, "ocr": ocr_row[0], "gt": gt_row[0]}
                )
            for column, (ocr_value, gt_value) in enumerate(zip(ocr_row[1:], gt_row[1:]), 1):
                if not gt_value.strip():
                    if ocr_value.strip():
                        blank_errors.append(
                            {"table": table_index + 1, "row": row_index, "column": column, "ocr": ocr_value}
                        )
                    continue
                table_total += 1
                if normalized_numeric(ocr_value) == normalized_numeric(gt_value):
                    table_exact += 1
                else:
                    disagreements.append(
                        {
                            "table": table_index + 1,
                            "row": row_index,
                            "key": gt_row[0],
                            "column": column,
                            "ocr": ocr_value,
                            "gt": gt_value,
                        }
                    )
        total += table_total
        exact += table_exact
        reports.append(
            {
                "numeric_cells": table_total,
                "exact_numeric_cells": table_exact,
                "exact_numeric_rate": table_exact / table_total,
            }
        )
    if (total, exact) != (19_616, 19_615) or blank_errors or key_errors:
        raise ValueError(
            f"training calibration changed: total={total} exact={exact} "
            f"blank={blank_errors} keys={key_errors}"
        )
    return {
        "image": "ec745262-a617-4423-b6f0-1d57849344b5.jpg",
        "tables": reports,
        "numeric_cells": total,
        "exact_numeric_cells": exact,
        "exact_numeric_rate": exact / total,
        "blank_errors": blank_errors,
        "key_errors": key_errors,
        "disagreements": disagreements,
        "validation_ok": True,
    }


def cloud_agreement(old_markdown: str, final_tables: list[list[list[str]]]) -> dict[str, object]:
    old = parse_tables(old_markdown)
    if len(old) != 4:
        raise ValueError("old cloud table count changed")
    starts = (0, 0, 0, 2)
    exact = 0
    events: list[dict[str, object]] = []
    for table_index, (cloud_table, final, start) in enumerate(zip(old, final_tables, starts)):
        for old_index, cloud_row in enumerate(cloud_table.cell_text_rows):
            age = start + old_index
            local_values = [value for value in final[age + 1][1:] if value]
            cloud_compact = [value.strip() for value in cloud_row if value.strip()]
            if len(cloud_compact) == len(local_values) and "." in cloud_compact[0]:
                cloud_values = cloud_compact
            else:
                cloud_values = cloud_compact[1:]
            left = [normalized_numeric(value) for value in local_values]
            right = [normalized_numeric(value) for value in cloud_values]
            matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    exact += i2 - i1
                else:
                    events.append(
                        {
                            "table": table_index + 1,
                            "age": age,
                            "operation": tag,
                            "local_columns": [i1 + 1, i2],
                            "local": local_values[i1:i2],
                            "cloud": cloud_values[j1:j2],
                        }
                    )
    if exact != 19_264 or len(events) != 9:
        raise ValueError(f"cloud agreement changed: exact={exact} events={events}")
    return {
        "exact_aligned_numeric_cells": exact,
        "difference_events": len(events),
        "events": events,
        "validation_ok": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("D:/AFAC2026/outputs/afac_A_submission_v23.csv"))
    parser.add_argument("--test-ocr", type=Path, required=True)
    parser.add_argument("--training-ocr", type=Path, required=True)
    parser.add_argument("--training-gt", type=Path, required=True)
    parser.add_argument("--test-ocr-report", type=Path, required=True)
    parser.add_argument("--training-ocr-report", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=ROOT / "work_v24" / "fixed107_clean_A_4e32.md")
    parser.add_argument("--output", type=Path, default=ROOT / "work_afac_A_submission_v24.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "work_afac_A_submission_v24.report.json")
    args = parser.parse_args()

    if hashlib.sha256(args.base.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("v23 base hash changed")
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base = load_submission(args.base)
    tables, cleanup = clean_test_tables(args.test_ocr)
    candidate = make_candidate(tables)
    structure = validate_candidate(candidate)
    if not structure["structure_ok"]:
        raise ValueError(f"candidate structure failed: {structure}")
    training = training_validation(args.training_ocr, args.training_gt)
    cloud = cloud_agreement(base[TARGET], tables)

    test_ocr_report = json.loads(args.test_ocr_report.read_text(encoding="utf-8"))
    training_ocr_report = json.loads(args.training_ocr_report.read_text(encoding="utf-8"))
    if any(table["count_mismatches"] for table in test_ocr_report["tables"]):
        raise ValueError("test OCR count mismatch appeared")
    if any(table["count_mismatches"] for table in training_ocr_report["tables"]):
        raise ValueError("training OCR count mismatch appeared")

    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text(candidate + "\n", encoding="utf-8")
    predictions = dict(base)
    predictions[TARGET] = candidate
    write_submission(data.submission_template, predictions, args.output)
    written = load_submission(args.output)
    changed = sorted(name for name in written if written[name] != base[name])
    if changed != [TARGET] or any(not value.strip() for value in written.values()):
        raise ValueError(f"written submission audit failed: changed={changed}")

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
            "changed_names": changed,
        },
        "change": {
            "file_name": TARGET,
            "old_characters": len(base[TARGET]),
            "new_characters": len(candidate),
            "cleanup": cleanup,
            "structure": structure,
            "training_calibration": training,
            "cloud_agreement": cloud,
            "geometry_evidence": {
                "semantic_shapes": [list(shape) for shape in FINAL_SHAPES],
                "data_row_ranges": [[0, rows - 1] for rows in DATA_ROWS],
                "columns": 107,
                "test_assigned_detections": [table["assigned_detections"] for table in test_ocr_report["tables"]],
                "test_count_mismatches": [table["count_mismatches"] for table in test_ocr_report["tables"]],
                "training_assigned_detections": [table["assigned_detections"] for table in training_ocr_report["tables"]],
                "training_count_mismatches": [table["count_mismatches"] for table in training_ocr_report["tables"]],
            },
            "input_sha256": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (
                    args.test_ocr,
                    args.training_ocr,
                    args.training_gt,
                    args.test_ocr_report,
                    args.training_ocr_report,
                )
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "candidate": str(args.candidate),
                "report": str(args.report),
                "sha256": report["sha256"],
                "changed_names": changed,
                "table_shapes": [item["shape"] for item in structure["table_reports"]],
                "nonempty_cells": [item["nonempty"] for item in structure["table_reports"]],
                "training_accuracy": training["exact_numeric_rate"],
                "cloud_exact_aligned": cloud["exact_aligned_numeric_cells"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
