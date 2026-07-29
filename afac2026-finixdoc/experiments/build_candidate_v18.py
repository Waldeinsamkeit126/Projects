from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402
from audit_two_triangular_integer_tables import parse_tables  # noqa: E402


TARGET = "d1752e16-eb38-4504-bd3f-45afaba26bba.jpg"
NUMERIC_COLUMNS = 71
TERMINAL = 106
EXPECTED_NONEMPTY = 12_247
TABLE_SPECS = (
    {"first_key": 56, "last_key": 106, "header": False},
    {"first_key": 1, "last_key": 106, "header": True},
    {"first_key": 1, "last_key": 106, "header": True},
    {"first_key": 1, "last_key": 5, "header": True},
)

OCR_DIGIT_TRANSLATION = str.maketrans(
    {
        "A": "4",
        "Z": "7",
        "z": "7",
        "L": "1",
        "l": "1",
        "I": "1",
        "i": "1",
        "J": "1",
        "f": "1",
        "d": "4",
        "g": "9",
        "E": "8",
        "O": "0",
        "o": "0",
        "M": "4",
        "s": "5",
    }
)


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected columns: {reader.fieldnames}")
        rows = list(reader)
    predictions = {
        str(row["file_name"]): str(row["ground_truth"]) for row in rows
    }
    if len(rows) != 100 or len(predictions) != 100:
        raise ValueError(
            f"base must contain 100 unique samples: rows={len(rows)} "
            f"unique={len(predictions)}"
        )
    return predictions


def canonical_digits(value: str) -> str:
    translated = value.translate(OCR_DIGIT_TRANSLATION)
    return re.sub(r"\D", "", translated)


def numeric_value(value: str) -> str:
    digits = canonical_digits(value)
    if len(digits) < 3:
        raise ValueError(f"numeric cell has fewer than three digits: {value!r}")
    integer = f"{int(digits[:-2]):,}"
    return f"{integer}.{digits[-2:]}"


def parse_numeric_grid(path: Path, rows: int) -> list[list[str]]:
    tables = parse_tables(path.read_text(encoding="utf-8"))
    if len(tables) != 1:
        raise ValueError(f"{path} contains {len(tables)} tables")
    values = [list(map(str.strip, row)) for row in tables[0].cell_text_rows]
    if len(values) != rows or any(len(row) != NUMERIC_COLUMNS for row in values):
        raise ValueError(f"unexpected physical grid shape in {path}")
    return values


def expected_numeric_count(key: int) -> int:
    return max(0, min(NUMERIC_COLUMNS, TERMINAL - key))


def clean_numeric_grids(paths: tuple[Path, ...]) -> tuple[list[list[list[str]]], dict[str, int]]:
    grids: list[list[list[str]]] = []
    translated_letter_cells = 0
    normalized_punctuation_cells = 0
    for path, spec in zip(paths, TABLE_SPECS):
        first_key = int(spec["first_key"])
        last_key = int(spec["last_key"])
        raw_rows = parse_numeric_grid(path, last_key - first_key + 1)
        clean_rows: list[list[str]] = []
        for row_index, (key, raw_row) in enumerate(
            zip(range(first_key, last_key + 1), raw_rows)
        ):
            count = expected_numeric_count(key)
            missing = [column for column, cell in enumerate(raw_row[:count]) if not cell]
            overflow = [
                [column, cell]
                for column, cell in enumerate(raw_row[count:], count)
                if cell
            ]
            if missing or overflow:
                raise ValueError(
                    f"physical prefix mismatch {path} row={row_index} key={key}: "
                    f"missing={missing} overflow={overflow}"
                )
            clean: list[str] = []
            for raw in raw_row[:count]:
                if any(ord(character) in OCR_DIGIT_TRANSLATION for character in raw):
                    translated_letter_cells += 1
                new = numeric_value(raw)
                if new != raw:
                    normalized_punctuation_cells += 1
                clean.append(new)
            clean_rows.append(clean)
        grids.append(clean_rows)
    return grids, {
        "translated_letter_cells": translated_letter_cells,
        "normalized_punctuation_cells": normalized_punctuation_cells,
    }


def cloud_tokens(row: list[str]) -> list[str]:
    result: list[str] = []
    for raw in row:
        if not raw.strip():
            continue
        digits = canonical_digits(raw)
        if len(digits) >= 3:
            result.append(digits)
    return result


def exact_alignment_size(local: list[str], cloud: list[str]) -> int:
    return sum(
        block.size
        for block in difflib.SequenceMatcher(
            None, local, cloud, autojunk=False
        ).get_matching_blocks()
    )


def choose_contiguous_offset(
    local_rows: list[list[str]], cloud_rows: list[list[str]]
) -> tuple[int, dict[str, object]]:
    if len(cloud_rows) > len(local_rows):
        raise ValueError("cloud table has more rows than the physical grid")
    local_digits = [[canonical_digits(value) for value in row] for row in local_rows]
    cloud_digits = [cloud_tokens(row) for row in cloud_rows]
    scores: list[tuple[int, int]] = []
    for offset in range(len(local_rows) - len(cloud_rows) + 1):
        score = sum(
            exact_alignment_size(local_digits[offset + index], cloud)
            for index, cloud in enumerate(cloud_digits)
        )
        scores.append((score, offset))
    ranked = sorted(scores, reverse=True)
    best_score, best_offset = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else -1
    return best_offset, {
        "offset": best_offset,
        "exact_anchor_cells": best_score,
        "runner_up_anchor_cells": runner_up,
        "anchor_margin": best_score - runner_up,
    }


def align_cloud_table(
    local_rows: list[list[str]], cloud_rows: list[list[str]]
) -> tuple[dict[tuple[int, int], str], dict[str, object]]:
    offset, offset_report = choose_contiguous_offset(local_rows, cloud_rows)
    observations: dict[tuple[int, int], str] = {}
    exact = replaced = skipped_replace = 0
    row_reports: list[dict[str, object]] = []
    for cloud_index, raw_cloud_row in enumerate(cloud_rows):
        local_index = offset + cloud_index
        local = [canonical_digits(value) for value in local_rows[local_index]]
        cloud = cloud_tokens(raw_cloud_row)
        matcher = difflib.SequenceMatcher(None, local, cloud, autojunk=False)
        row_exact = row_replaced = 0
        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if tag == "equal":
                for left, right in zip(
                    range(left_start, left_end), range(right_start, right_end)
                ):
                    observations[(local_index, left)] = cloud[right]
                    exact += 1
                    row_exact += 1
            elif tag == "replace" and left_end - left_start == right_end - right_start:
                for left, right in zip(
                    range(left_start, left_end), range(right_start, right_end)
                ):
                    observations[(local_index, left)] = cloud[right]
                    replaced += 1
                    row_replaced += 1
            elif tag == "replace":
                skipped_replace += max(left_end - left_start, right_end - right_start)
        row_reports.append(
            {
                "cloud_row": cloud_index,
                "local_row": local_index,
                "local_cells": len(local),
                "cloud_tokens": len(cloud),
                "exact": row_exact,
                "positionally_replaced": row_replaced,
            }
        )
    return observations, {
        **offset_report,
        "local_rows": len(local_rows),
        "cloud_rows": len(cloud_rows),
        "observations": len(observations),
        "exact_observations": exact,
        "positionally_replaced_observations": replaced,
        "skipped_unequal_replace_tokens": skipped_replace,
        "row_reports": row_reports,
    }


def cloud_tables(markdown: str) -> list[list[list[str]]]:
    tables = parse_tables(markdown)
    if len(tables) != len(TABLE_SPECS):
        raise ValueError(f"expected four old cloud tables, found {len(tables)}")
    return [table.cell_text_rows for table in tables]


def apply_duplicate_consensus(
    grids: list[list[list[str]]],
    cloud_observations: list[dict[tuple[int, int], str]],
) -> dict[str, object]:
    # Table 1 is the key-56..106 continuation of table 3.  The two physical
    # prints and the two cloud parses are independent observations of the same
    # cells, which makes majority repair substantially safer than smoothing.
    original1 = [
        [canonical_digits(value) for value in row] for row in grids[0]
    ]
    original3 = [
        [canonical_digits(value) for value in row] for row in grids[2]
    ]
    decisions: Counter[str] = Counter()
    disagreements: list[dict[str, object]] = []
    ties: list[dict[str, object]] = []
    for table1_row, key in enumerate(range(56, 107)):
        table3_row = key - 1
        for column in range(expected_numeric_count(key)):
            local1 = canonical_digits(grids[0][table1_row][column])
            local3 = canonical_digits(grids[2][table3_row][column])
            observations = [local1, local3]
            cloud1 = cloud_observations[0].get((table1_row, column))
            cloud3 = cloud_observations[2].get((table3_row, column))
            if cloud1:
                observations.append(cloud1)
            if cloud3:
                observations.append(cloud3)
            counts = Counter(observations)
            highest = max(counts.values())
            winners = {value for value, count in counts.items() if count == highest}
            if local1 == local3 and local1 in winners:
                chosen = local1
                reason = "local_agreement"
            elif len(winners) == 1 and highest >= 2:
                chosen = next(iter(winners))
                reason = "unique_majority"
            elif local1 in winners:
                chosen = local1
                reason = "tie_keep_table1"
            else:
                chosen = local1
                reason = "no_majority_keep_table1"
            decisions[reason] += 1
            formatted = numeric_value(chosen)
            grids[0][table1_row][column] = formatted
            grids[2][table3_row][column] = formatted
            sample: dict[str, object] | None = None
            if local1 != local3 and len(disagreements) < 160:
                sample = {
                    "key": key,
                    "column": column,
                    "local_table1": local1,
                    "local_table3": local3,
                    "cloud_table1": cloud1,
                    "cloud_table3": cloud3,
                    "chosen": chosen,
                    "reason": reason,
                    "votes": dict(counts),
                }
                disagreements.append(sample)
            if reason == "tie_keep_table1" and local1 != local3:
                ties.append(
                    {
                        "table1_row": table1_row,
                        "table3_row": table3_row,
                        "column": column,
                        "candidates": sorted(winners),
                        "sample": sample,
                    }
                )

    # When the two local parses and two cloud parses split 2-2, choose the
    # candidate closest to a linear interpolation between the nearest
    # non-tied cells in that printed row.  These schedules are locally smooth;
    # the ambiguous alternatives usually differ by hundreds or thousands.
    tied_by_row: dict[int, set[int]] = {}
    for item in ties:
        tied_by_row.setdefault(int(item["table1_row"]), set()).add(
            int(item["column"])
        )
    tie_smoothing: Counter[str] = Counter()
    for item in ties:
        row = int(item["table1_row"])
        table3_row = int(item["table3_row"])
        column = int(item["column"])
        tied_columns = tied_by_row[row]
        usable = [
            index
            for index in range(len(grids[0][row]))
            if index not in tied_columns
        ]
        left = max((index for index in usable if index < column), default=None)
        right = min((index for index in usable if index > column), default=None)
        candidates = [str(value) for value in item["candidates"]]  # type: ignore[index]
        chosen = original1[row][column]
        predicted: float | None = None
        if left is not None and right is not None:
            left_value = int(canonical_digits(grids[0][row][left]))
            right_value = int(canonical_digits(grids[0][row][right]))
            predicted = left_value + (right_value - left_value) * (
                (column - left) / (right - left)
            )
            chosen = min(
                candidates,
                key=lambda value: (abs(int(value) - predicted), value != original1[row][column]),
            )
        grids[0][row][column] = numeric_value(chosen)
        grids[2][table3_row][column] = numeric_value(chosen)
        source = (
            "table1"
            if chosen == original1[row][column]
            else "table3"
            if chosen == original3[table3_row][column]
            else "other"
        )
        tie_smoothing[source] += 1
        sample = item.get("sample")
        if isinstance(sample, dict):
            sample["chosen"] = chosen
            sample["reason"] = "tie_smoothed"
            sample["interpolation"] = {
                "left_column": left,
                "right_column": right,
                "predicted_digits": round(predicted, 3) if predicted is not None else None,
                "selected_source": source,
            }

    changes = [
        sum(
            canonical_digits(value) != original
            for row, originals in zip(grids[0], original1)
            for value, original in zip(row, originals)
        ),
        sum(
            canonical_digits(value) != original
            for row, originals in zip(grids[2], original3)
            for value, original in zip(row, originals)
        ),
    ]
    return {
        "duplicate_cells": sum(expected_numeric_count(key) for key in range(56, 107)),
        "changed_table1_cells": changes[0],
        "changed_table3_cells": changes[1],
        "decision_counts": dict(decisions),
        "tie_smoothing_selected_sources": dict(tie_smoothing),
        "disagreement_samples": disagreements,
    }


def header_row() -> list[str]:
    return ["保单年度\\投保年龄", *[str(value) for value in range(NUMERIC_COLUMNS)]]


def semantic_rows(
    numeric_rows: list[list[str]], spec: dict[str, object]
) -> list[list[str]]:
    first_key = int(spec["first_key"])
    last_key = int(spec["last_key"])
    result = [header_row()] if bool(spec["header"]) else []
    for key, numeric in zip(range(first_key, last_key + 1), numeric_rows):
        count = expected_numeric_count(key)
        if len(numeric) != count:
            raise ValueError(f"numeric count changed for key {key}: {len(numeric)} != {count}")
        values = [str(key), *numeric]
        if count < NUMERIC_COLUMNS:
            values.append("-")
        values.extend([""] * (NUMERIC_COLUMNS + 1 - len(values)))
        if len(values) != NUMERIC_COLUMNS + 1:
            raise ValueError(f"semantic row width changed for key {key}")
        result.append(values)
    return result


def serialize_table(rows: list[list[str]], has_header: bool) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row_index, row in enumerate(rows):
        tag = "th" if has_header and row_index == 0 else "td"
        cells = "".join(
            f"<{tag}>{html.escape(cell)}</{tag}>" for cell in row
        )
        lines.append(f"      <tr>{cells}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def structure_report(markdown: str) -> dict[str, object]:
    tables = parse_tables(markdown)
    expected_shapes = [(51, 72), (107, 72), (107, 72), (6, 72)]
    actual_shapes = [
        [len(table.cell_text_rows), sorted(set(map(len, table.cell_text_rows)))]
        for table in tables
    ]
    shape_ok = len(tables) == 4 and all(
        len(table.cell_text_rows) == rows
        and all(len(row) == columns for row in table.cell_text_rows)
        for table, (rows, columns) in zip(tables, expected_shapes)
    )
    header_tags_ok = len(tables) == 4 and all(
        all(
            all(cell == (("th" if spec["header"] and row_index == 0 else "td"), None, None) for cell in row)
            for row_index, row in enumerate(table.rows)
        )
        for table, spec in zip(tables, TABLE_SPECS)
    )
    nonempty = sum(
        bool(cell.strip())
        for table in tables
        for row in table.cell_text_rows
        for cell in row
    )
    outside = re.sub(r"<table[^>]*>.*?</table>", "", markdown, flags=re.I | re.S).strip()
    return {
        "tables": len(tables),
        "expected_shapes": expected_shapes,
        "actual_shapes": actual_shapes,
        "nonempty_cells": nonempty,
        "outside_text": outside,
        "header_tags_ok": header_tags_ok,
        "structure_ok": (
            shape_ok and header_tags_ok and nonempty == EXPECTED_NONEMPTY and not outside
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v17.csv"),
    )
    parser.add_argument(
        "--table1",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule51x71_A_d175_table1_strict.md"),
    )
    parser.add_argument(
        "--table2",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule106x71_A_d175_table2_strict.md"),
    )
    parser.add_argument(
        "--table3",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule106x71_A_d175_table3_strict.md"),
    )
    parser.add_argument(
        "--table4",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule5x71_A_d175_table4_strict.md"),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path("D:/AFAC2026/outputs/experiments/rule_combined_A_d175.md"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v18.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v18.report.json"),
    )
    args = parser.parse_args()

    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base_predictions = load_submission(args.base)
    old = base_predictions[TARGET]
    paths = (args.table1, args.table2, args.table3, args.table4)
    grids, cleanup = clean_numeric_grids(paths)
    old_tables = cloud_tables(old)
    cloud_observations: list[dict[tuple[int, int], str]] = []
    alignment_reports: list[dict[str, object]] = []
    for local, cloud in zip(grids, old_tables):
        observations, report = align_cloud_table(local, cloud)
        cloud_observations.append(observations)
        alignment_reports.append(report)
    consensus = apply_duplicate_consensus(grids, cloud_observations)
    tables = [
        serialize_table(semantic_rows(grid, spec), bool(spec["header"]))
        for grid, spec in zip(grids, TABLE_SPECS)
    ]
    candidate = "\n\n".join(tables)
    structure = structure_report(candidate)
    if not bool(structure["structure_ok"]):
        raise ValueError(f"candidate structure failed: {structure}")

    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text(candidate + "\n", encoding="utf-8")
    predictions = dict(base_predictions)
    predictions[TARGET] = candidate
    write_submission(data.submission_template, predictions, args.output)
    written = load_submission(args.output)
    changed_names = sorted(
        name for name, value in written.items() if value != base_predictions[name]
    )
    if changed_names != [TARGET]:
        raise ValueError(f"unexpected written changes: {changed_names}")
    if any(not value.strip() for value in written.values()):
        raise ValueError("submission contains a blank prediction")

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
            "added_characters": len(candidate) - len(old),
            "structure": structure,
            "cleanup": cleanup,
            "cloud_alignments": alignment_reports,
            "duplicate_consensus": consensus,
            "evidence": {
                "physical_grid_shapes": [[51, 71], [106, 71], [106, 71], [5, 71]],
                "semantic_table_shapes": [[51, 72], [107, 72], [107, 72], [6, 72]],
                "strict_physical_numeric_cells": [1275, 4970, 4970, 355],
                "training_tiny_exact_numeric_rate": 0.9408450704225352,
                "duplicate_relation": "table1 keys 56..106 equals table3 keys 56..106",
                "expected_numeric_formula": "max(0, min(71, 106 - row_key))",
                "diagonal_dash_formula": "one dash when numeric count is below 71",
            },
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": report["sha256"],
                "structure": structure,
                "cleanup": cleanup,
                "alignment_summary": [
                    {key: value for key, value in item.items() if key != "row_reports"}
                    for item in alignment_reports
                ],
                "consensus": {
                    key: value
                    for key, value in consensus.items()
                    if key != "disagreement_samples"
                },
                "changed_names": changed_names,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
