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
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402
from build_candidate_v24 import (  # noqa: E402
    load_submission,
    normalized_numeric,
    parse_tables,
    training_validation,
)


TARGET = "185a2337-c7a0-41f0-a283-a3d8c22a1041.jpg"
BASE_SHA256 = "abdcdd387d92d4188e37026670a03e7168916fa0522dbcfaf42d9f2a3e547d02"
FIRST_KEYS = (54, 0, 0)
DATA_ROWS = (12, 56, 56)
HAS_HEADER = (False, True, True)
FINAL_SHAPES = ((12, 107), (57, 107), (57, 107))
EXPECTED_RAW_NONEMPTY = (570, 4_452, 4_452)
EXPECTED_FINAL_NONEMPTY = (570, 4_559, 4_559)
HEADER_LABEL = "投保年龄\\保单年度末"
TABLE_TITLES = ("男性，20年交", "女性，20年交")


def clean_numeric(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value.strip()).upper()
    cleaned = cleaned.replace("B", "8").replace(",", ".")
    if re.fullmatch(r"[0-9]+\.[0-9]{2}", cleaned):
        whole, fraction = cleaned.split(".")
        return f"{int(whole)}.{fraction}"
    if re.fullmatch(r"[0-9]{3,}", cleaned):
        return f"{int(cleaned[:-2])}.{cleaned[-2:]}"
    raise ValueError(f"ambiguous numeric OCR value: {value!r}")


def header() -> list[str]:
    return [HEADER_LABEL, *map(str, range(1, 107))]


def clean_test_tables(raw_path: Path) -> tuple[list[list[list[str]]], dict[str, object]]:
    parsed = parse_tables(raw_path.read_text(encoding="utf-8"))
    if len(parsed) != 3:
        raise ValueError(f"local OCR table count changed: {len(parsed)}")
    final_tables: list[list[list[str]]] = []
    repairs: list[dict[str, object]] = []
    reports: list[dict[str, object]] = []
    for table_index, (table, first_key, rows_expected) in enumerate(
        zip(parsed, FIRST_KEYS, DATA_ROWS)
    ):
        raw = table.cell_text_rows
        if len(raw) != rows_expected or any(len(row) != 107 for row in raw):
            raise ValueError(f"test OCR shape changed at table {table_index + 1}")
        raw_nonempty = sum(bool(value.strip()) for row in raw for value in row)
        if raw_nonempty != EXPECTED_RAW_NONEMPTY[table_index]:
            raise ValueError(f"test OCR nonempty changed at table {table_index + 1}")
        final: list[list[str]] = [header()] if HAS_HEADER[table_index] else []
        for row_index, source_row in enumerate(raw):
            age = first_key + row_index
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
                value = clean_numeric(source)
                if value != source.strip():
                    repairs.append(
                        {
                            "table": table_index + 1,
                            "age": age,
                            "column": column,
                            "old": source,
                            "new": value,
                            "evidence": "deterministic punctuation normalization and cloud agreement",
                        }
                    )
                row.append(value)
            row.extend([""] * (107 - len(row)))
            final.append(row)
        nonempty = sum(bool(value) for row in final for value in row)
        if nonempty != EXPECTED_FINAL_NONEMPTY[table_index]:
            raise ValueError("cleaning changed the theoretical nonempty count")
        final_tables.append(final)
        reports.append(
            {
                "raw_rows": len(raw),
                "raw_columns": 107,
                "raw_nonempty": raw_nonempty,
                "final_rows": len(final),
                "final_columns": 107,
                "final_nonempty": nonempty,
                "key_range": [first_key, first_key + rows_expected - 1],
                "header_reconstructed": HAS_HEADER[table_index],
            }
        )
    if len(repairs) != 7:
        raise ValueError(f"punctuation repair count changed: {repairs}")
    return final_tables, {"tables": reports, "punctuation_repairs": repairs}


def serialize_table(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def make_candidate(tables: list[list[list[str]]]) -> str:
    return (
        serialize_table(tables[0])
        + "\n\n"
        + TABLE_TITLES[0]
        + "\n\n"
        + serialize_table(tables[1])
        + "\n\n"
        + TABLE_TITLES[1]
        + "\n\n"
        + serialize_table(tables[2])
    )


def validate_candidate(markdown: str) -> dict[str, object]:
    tables = parse_tables(markdown)
    outside = re.sub(r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S)
    outside_lines = [line.strip() for line in outside.splitlines() if line.strip()]
    reports: list[dict[str, object]] = []
    for table_index, table in enumerate(tables):
        rows = table.cell_text_rows
        shape = (len(rows), len(rows[0]) if rows else 0)
        data = rows[1:] if HAS_HEADER[table_index] else rows
        first_key = FIRST_KEYS[table_index]
        keys = [row[0] for row in data]
        prefix_ok = all(
            all(row[column] for column in range(107 - age))
            and not any(row[107 - age :])
            for age, row in zip(range(first_key, first_key + DATA_ROWS[table_index]), data)
        )
        numeric_ok = all(
            re.fullmatch(r"[0-9]+\.[0-9]{2}", value) is not None
            for age, row in zip(range(first_key, first_key + DATA_ROWS[table_index]), data)
            for value in row[1 : 107 - age]
        )
        nonempty = sum(bool(value) for row in rows for value in row)
        plain_td = all(row == [("td", None, None)] * 107 for row in table.rows)
        header_exact = not HAS_HEADER[table_index] or rows[0] == header()
        keys_exact = keys == list(map(str, range(first_key, first_key + DATA_ROWS[table_index])))
        ok = (
            shape == FINAL_SHAPES[table_index]
            and header_exact
            and keys_exact
            and prefix_ok
            and numeric_ok
            and nonempty == EXPECTED_FINAL_NONEMPTY[table_index]
            and plain_td
        )
        reports.append(
            {
                "shape": list(shape),
                "nonempty": nonempty,
                "header_exact": header_exact,
                "keys_exact": keys_exact,
                "prefix_exact": prefix_ok,
                "numeric_format_exact": numeric_ok,
                "plain_td_exact": plain_td,
                "structure_ok": ok,
            }
        )
    structure_ok = (
        len(tables) == 3
        and outside_lines == list(TABLE_TITLES)
        and all(report["structure_ok"] for report in reports)
    )
    return {
        "tables": len(tables),
        "outside_lines": outside_lines,
        "outside_exact": outside_lines == list(TABLE_TITLES),
        "table_reports": reports,
        "structure_ok": structure_ok,
    }


def cloud_agreement(old_markdown: str, final: list[list[list[str]]]) -> dict[str, object]:
    old = parse_tables(old_markdown)
    if len(old) != 4:
        raise ValueError("old cloud table count changed")
    mappings: list[tuple[int, list[tuple[int, list[str], bool]]]] = [
        (0, [(55 + index, row, False) for index, row in enumerate(old[0].cell_text_rows)]),
        (1, [(index, row, True) for index, row in enumerate(old[1].cell_text_rows)]),
    ]
    female = [(index, row, True) for index, row in enumerate(old[2].cell_text_rows)]
    female.extend((5 + index, row, False) for index, row in enumerate(old[3].cell_text_rows))
    mappings.append((2, female))

    exact = 0
    events: list[dict[str, object]] = []
    for table_index, rows in mappings:
        offset = 54 if table_index == 0 else 0
        header_offset = 1 if HAS_HEADER[table_index] else 0
        for age, cloud_row, force_all in rows:
            local = [value for value in final[table_index][header_offset + age - offset][1:] if value]
            compact = [value.strip() for value in cloud_row if value.strip()]
            cloud = compact if force_all or not compact or compact[0] != str(age) else compact[1:]
            left = [normalized_numeric(value) for value in local]
            right = [normalized_numeric(value) for value in cloud]
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
                            "local": local[i1:i2],
                            "cloud": cloud[j1:j2],
                        }
                    )
    if exact != 8_989 or len(events) != 112:
        raise ValueError(f"cloud agreement changed: exact={exact} events={len(events)}")
    if any(event["operation"] != "insert" or event["local"] for event in events):
        raise ValueError("cloud differences are no longer insertion-only")
    return {
        "exact_aligned_numeric_cells": exact,
        "difference_events": len(events),
        "all_differences_are_cloud_insertions": True,
        "events": events,
        "validation_ok": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("D:/AFAC2026/outputs/afac_A_submission_v24.csv"))
    parser.add_argument("--test-ocr", type=Path, required=True)
    parser.add_argument("--training-ocr", type=Path, required=True)
    parser.add_argument("--training-gt", type=Path, required=True)
    parser.add_argument("--test-ocr-report", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=ROOT / "work_v25" / "fixed107_clean_A_185a.md")
    parser.add_argument("--output", type=Path, default=ROOT / "work_afac_A_submission_v25.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "work_afac_A_submission_v25.report.json")
    args = parser.parse_args()

    if hashlib.sha256(args.base.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("v24 base hash changed")
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
    ocr_report = json.loads(args.test_ocr_report.read_text(encoding="utf-8"))
    if any(table["count_mismatches"] for table in ocr_report["tables"]):
        raise ValueError("test OCR count mismatch appeared")

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
                "data_row_ranges": [[start, start + rows - 1] for start, rows in zip(FIRST_KEYS, DATA_ROWS)],
                "columns": 107,
                "assigned_detections": [table["assigned_detections"] for table in ocr_report["tables"]],
                "count_mismatches": [table["count_mismatches"] for table in ocr_report["tables"]],
            },
            "input_sha256": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (args.test_ocr, args.training_ocr, args.training_gt, args.test_ocr_report)
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
