from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402
from build_candidate_v24 import load_submission, parse_tables  # noqa: E402


TARGET = "baf9a56f-852d-4d4f-be57-581d3e16468e.jpg"
BASE_SHA256 = "8420702df16427be9939664386e45fec0d6e7d53af1641973866e359b01d3426"
TITLE = "信泰如意福享（2026）养老年金保险（互联网专属）现金价值全表（每1000元趸交或年交保费）"
TABLE_LABELS = ("男性", "女性")
HEADER_LABEL = "保单年度\\投保年龄"
ROWS = (106, 81)
FINAL_SHAPES = ((107, 82), (82, 82))
EXPECTED_NONEMPTY = (5_453, 5_128)

# Fixed geometry is directly visible in the source page: one key column followed
# by ages 0..80, with 14-pixel row pitch in both stacked tables.
DATA_X0 = 245.0
DATA_X_STEP = 52.68
DATA_X_TOLERANCE = 23.0
ROW_Y0 = (365.5, 1877.5)
ROW_Y_STEP = 14.0
ROW_Y_TOLERANCE = 6.0

# These six cells were the only places where both independent OCR passes were
# blank/incomplete.  Their values are legible in saved source crops with
# neighbouring headers and values on both sides.
SOURCE_REPAIRS = {
    (0, 1, 35): "507.77",
    (1, 1, 21): "425.20",
    (1, 1, 31): "491.68",
    (1, 1, 35): "512.25",
    (1, 1, 57): "644.45",
    (1, 1, 75): "778.44",
}


def canonical_numeric(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value.strip()).replace(",", ".")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    if re.fullmatch(r"[0-9]+", cleaned):
        return str(int(cleaned))
    match = re.fullmatch(r"([0-9]+)\.([0-9]{1,2})", cleaned)
    if match:
        return f"{int(match.group(1))}.{match.group(2).ljust(2, '0')}"
    raise ValueError(f"ambiguous numeric OCR value: {value!r}")


def digit_signature(value: str) -> str:
    return "".join(re.findall(r"[0-9]", value))


def detection_text(pieces: list[dict[str, object]]) -> str:
    ordered = sorted(pieces, key=lambda item: float(item["left"]))
    signatures = [digit_signature(str(item["text"])) for item in ordered]
    if signatures and all(value == signatures[0] for value in signatures):
        return str(ordered[0]["text"])
    return "".join(str(item["text"]).strip() for item in ordered)


def expected_data_cells(year: int) -> int:
    return min(81, 106 - year)


def map_local_detections(
    detections: list[dict[str, object]], table_index: int, year: int
) -> dict[int, list[dict[str, object]]]:
    center_y = ROW_Y0[table_index] + ROW_Y_STEP * (year - 1)
    result: dict[int, list[dict[str, object]]] = defaultdict(list)
    for item in detections:
        x = (float(item["left"]) + float(item["right"])) / 2
        y = (float(item["top"]) + float(item["bottom"])) / 2
        if abs(y - center_y) > ROW_Y_TOLERANCE or not 222.0 < x < 4490.0:
            continue
        column = round((x - DATA_X0) / DATA_X_STEP)
        if not 0 <= column < 81:
            continue
        if abs(x - (DATA_X0 + DATA_X_STEP * column)) > DATA_X_TOLERANCE:
            continue
        result[column].append(item)
    return result


def header() -> list[str]:
    return [HEADER_LABEL, *map(str, range(81))]


def reconstruct_tables(
    old_markdown: str, raw_report: dict[str, object]
) -> tuple[list[list[list[str]]], dict[str, object]]:
    old_tables = parse_tables(old_markdown)
    if len(old_tables) != 2:
        raise ValueError(f"old table count changed: {len(old_tables)}")
    old_rows = [table.cell_text_rows for table in old_tables]
    if [(len(rows), len(rows[0])) for rows in old_rows] != [(103, 82), (82, 82)]:
        raise ValueError("old baf9 table shapes changed")
    detections = list(raw_report["detections"])

    final_tables: list[list[list[str]]] = []
    source_counts: dict[str, int] = defaultdict(int)
    agreement = {
        "exact_digit_signatures": 0,
        "format_only_differences": 0,
        "content_differences": 0,
        "local_only": 0,
        "old_only": 0,
        "manual_source_repairs": 0,
    }
    difference_examples: list[dict[str, object]] = []
    table_reports: list[dict[str, object]] = []

    for table_index, row_count in enumerate(ROWS):
        rows = [header()]
        for year in range(1, row_count + 1):
            expected = expected_data_cells(year)
            mapped = map_local_detections(detections, table_index, year)
            row = [str(year)]
            for age in range(expected):
                local_raw = detection_text(mapped[age]) if mapped.get(age) else ""
                old_raw = (
                    old_rows[table_index][year][age + 1]
                    if year < len(old_rows[table_index])
                    else ""
                )
                repair = SOURCE_REPAIRS.get((table_index, year, age))
                if repair is not None:
                    selected = repair
                    source = "source_crop"
                    agreement["manual_source_repairs"] += 1
                elif local_raw:
                    selected = canonical_numeric(local_raw)
                    source = "fixed_geometry_local"
                elif old_raw:
                    selected = canonical_numeric(old_raw)
                    source = "old_cell_fallback"
                else:
                    raise ValueError(
                        f"unresolved cell table={table_index + 1} year={year} age={age}"
                    )
                source_counts[source] += 1
                row.append(selected)

                if local_raw and old_raw:
                    if digit_signature(local_raw) == digit_signature(old_raw):
                        agreement["exact_digit_signatures"] += 1
                        if re.sub(r"\s+", "", local_raw) != re.sub(r"\s+", "", old_raw):
                            agreement["format_only_differences"] += 1
                    else:
                        agreement["content_differences"] += 1
                        if len(difference_examples) < 50:
                            difference_examples.append(
                                {
                                    "table": table_index + 1,
                                    "year": year,
                                    "age": age,
                                    "old": old_raw,
                                    "local": local_raw,
                                    "selected": selected,
                                }
                            )
                elif local_raw:
                    agreement["local_only"] += 1
                elif old_raw:
                    agreement["old_only"] += 1
            row.extend([""] * (82 - len(row)))
            rows.append(row)

        nonempty = sum(bool(value) for row in rows for value in row)
        prefix_exact = all(
            all(row[: 1 + expected_data_cells(year)])
            and not any(row[1 + expected_data_cells(year) :])
            for year, row in enumerate(rows[1:], 1)
        )
        numeric_exact = all(
            re.fullmatch(r"[0-9]+(?:\.[0-9]{2})?", value) is not None
            for year, row in enumerate(rows[1:], 1)
            for value in row[1 : 1 + expected_data_cells(year)]
        )
        report = {
            "shape": [len(rows), len(rows[0])],
            "header_exact": rows[0] == header(),
            "keys_exact": [row[0] for row in rows[1:]] == list(map(str, range(1, row_count + 1))),
            "prefix_exact": prefix_exact,
            "numeric_format_exact": numeric_exact,
            "nonempty": nonempty,
            "structure_ok": (
                (len(rows), len(rows[0])) == FINAL_SHAPES[table_index]
                and rows[0] == header()
                and prefix_exact
                and numeric_exact
                and nonempty == EXPECTED_NONEMPTY[table_index]
            ),
        }
        table_reports.append(report)
        final_tables.append(rows)

    if agreement != {
        "exact_digit_signatures": 10_112,
        "format_only_differences": 14,
        "content_differences": 41,
        "local_only": 60,
        "old_only": 12,
        "manual_source_repairs": 6,
    }:
        raise ValueError(f"local/old agreement changed: {agreement}")
    if not all(report["structure_ok"] for report in table_reports):
        raise ValueError(f"candidate table validation failed: {table_reports}")
    return final_tables, {
        "tables": table_reports,
        "selected_cell_sources": dict(source_counts),
        "local_old_agreement": agreement,
        "difference_examples": difference_examples,
        "source_repairs": [
            {
                "table": table + 1,
                "year": year,
                "age": age,
                "value": value,
                "evidence": "source crop with adjacent headers and values",
            }
            for (table, year, age), value in sorted(SOURCE_REPAIRS.items())
        ],
    }


def serialize_table(rows: list[list[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in rows:
        cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def make_candidate(tables: list[list[list[str]]]) -> str:
    return (
        TITLE
        + "\n\n"
        + TABLE_LABELS[0]
        + "\n\n"
        + serialize_table(tables[0])
        + "\n\n"
        + TABLE_LABELS[1]
        + "\n\n"
        + serialize_table(tables[1])
    )


def validate_candidate(markdown: str) -> dict[str, object]:
    tables = parse_tables(markdown)
    outside = re.sub(r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S)
    outside_lines = [line.strip() for line in outside.splitlines() if line.strip()]
    shapes = [
        [len(table.cell_text_rows), len(table.cell_text_rows[0])]
        for table in tables
    ]
    plain_td = all(
        all(row == [("td", None, None)] * 82 for row in table.rows)
        for table in tables
    )
    ok = (
        len(tables) == 2
        and outside_lines == [TITLE, *TABLE_LABELS]
        and shapes == [list(shape) for shape in FINAL_SHAPES]
        and plain_td
    )
    return {
        "tables": len(tables),
        "outside_lines": outside_lines,
        "outside_exact": outside_lines == [TITLE, *TABLE_LABELS],
        "shapes": shapes,
        "plain_td_exact": plain_td,
        "structure_ok": ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("D:/AFAC2026/outputs/afac_A_submission_v25.csv"))
    parser.add_argument("--raw-ocr", type=Path, default=ROOT / "work_v25" / "baf9_page_ocr.json")
    parser.add_argument("--candidate", type=Path, default=ROOT / "work_v26" / "fixed_geometry_A_baf9.md")
    parser.add_argument("--output", type=Path, default=ROOT / "work_afac_A_submission_v26.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "work_afac_A_submission_v26.report.json")
    args = parser.parse_args()

    if hashlib.sha256(args.base.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("v25 base hash changed")
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base = load_submission(args.base)
    raw_report = json.loads(args.raw_ocr.read_text(encoding="utf-8"))
    if len(raw_report["detections"]) != 10_527:
        raise ValueError("raw OCR detection count changed")

    tables, reconstruction = reconstruct_tables(base[TARGET], raw_report)
    candidate = make_candidate(tables)
    structure = validate_candidate(candidate)
    if not structure["structure_ok"]:
        raise ValueError(f"candidate structure failed: {structure}")

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
            "old_shapes": [[103, 82], [82, 82]],
            "new_shapes": [list(shape) for shape in FINAL_SHAPES],
            "structure": structure,
            "reconstruction": reconstruction,
            "geometry": {
                "data_x0": DATA_X0,
                "data_x_step": DATA_X_STEP,
                "row_y0": list(ROW_Y0),
                "row_y_step": ROW_Y_STEP,
                "columns": 82,
                "header_ages": [0, 80],
                "year_ranges": [[1, 106], [1, 81]],
            },
            "raw_ocr": {
                "path": str(args.raw_ocr),
                "sha256": hashlib.sha256(args.raw_ocr.read_bytes()).hexdigest(),
                "detections": len(raw_report["detections"]),
                "tiles": raw_report["ocr"]["tiles"],
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
                "table_shapes": reconstruction["tables"],
                "selected_cell_sources": reconstruction["selected_cell_sources"],
                "local_old_agreement": reconstruction["local_old_agreement"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
