from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.score import _TableParser  # noqa: E402


def load_prediction(path: Path, image_name: str) -> str:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        matches = [
            str(row["ground_truth"])
            for row in csv.DictReader(stream)
            if str(row["file_name"]) == image_name
        ]
    if len(matches) != 1:
        raise ValueError(f"expected one submission row, found {len(matches)}")
    return matches[0]


def parse_rows(markdown: str) -> list[list[str]]:
    parsed = _TableParser()
    parsed.feed(markdown)
    if parsed.tables != 1:
        raise ValueError(f"expected one table, found {parsed.tables}")
    return parsed.cell_text_rows


def normalize(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
        return value
    if re.fullmatch(r"[0-9\s,.:，。]+", value):
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 3:
            return f"{digits[:-2]}.{digits[-2:]}"
        if digits == "0":
            return "0.00"
    return value


def blank_runs(row: list[str], end: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for column in range(4, end):
        if not row[column].strip() and start is None:
            start = column
        elif row[column].strip() and start is not None:
            runs.append((start, column - 1))
            start = None
    if start is not None:
        runs.append((start, end - 1))
    return runs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_name")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--candidate-header-rows", type=int, default=1)
    parser.add_argument("--submission-header-rows", type=int, default=2)
    parser.add_argument("--candidate-repair", action="append", default=[])
    parser.add_argument("--submission-repair", action="append", default=[])
    parser.add_argument("--expected-candidate-repairs", type=int, default=0)
    parser.add_argument("--expected-recovered", type=int, required=True)
    args = parser.parse_args()

    candidate_markdown = args.candidate.read_text(encoding="utf-8")
    candidate_rows = parse_rows(candidate_markdown)
    old_rows = parse_rows(load_prediction(args.submission, args.image_name))
    candidate_data = candidate_rows[args.candidate_header_rows :]
    old_data = old_rows[args.submission_header_rows :]
    if len(candidate_data) != len(old_data):
        raise ValueError(
            f"data row mismatch: candidate={len(candidate_data)} old={len(old_data)}"
        )

    candidate_repairs: list[dict[str, object]] = []
    for specification in args.candidate_repair:
        parts = specification.split(":", 3)
        if len(parts) != 4:
            raise ValueError(
                "candidate repair must be ROW:COLUMN:OLD:NEW: "
                f"{specification!r}"
            )
        row_index, column_index = int(parts[0]), int(parts[1])
        old, new = parts[2], parts[3]
        actual = candidate_data[row_index][column_index]
        if actual != old:
            raise ValueError(
                f"candidate repair mismatch at {row_index}:{column_index}: "
                f"expected={old!r} actual={actual!r}"
            )
        candidate_data[row_index][column_index] = new
        candidate_repairs.append(
            {
                "row": row_index,
                "column": column_index,
                "old": old,
                "new": new,
            }
        )
    if len(candidate_repairs) != args.expected_candidate_repairs:
        raise ValueError(
            f"expected {args.expected_candidate_repairs} candidate repairs, "
            f"found {len(candidate_repairs)}"
        )

    submission_repairs: dict[int, list[tuple[str, str]]] = {}
    for specification in args.submission_repair:
        parts = specification.split(":", 2)
        if len(parts) != 3:
            raise ValueError(
                f"submission repair must be ROW:OLD:NEW: {specification!r}"
            )
        submission_repairs.setdefault(int(parts[0]), []).append(
            (parts[1], parts[2])
        )

    recovered: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    applied_submission_repairs: list[dict[str, object]] = []
    for row_index, (candidate, old) in enumerate(zip(candidate_data, old_data)):
        age = int(candidate[2])
        expected_end = len(candidate) - age
        old_values = [normalize(value) for value in old if value.strip()]
        for old_value, new_value in submission_repairs.get(row_index, []):
            matches = [
                index for index, value in enumerate(old_values) if value == old_value
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"submission repair mismatch in row {row_index}: "
                    f"value={old_value!r} matches={matches}"
                )
            old_values[matches[0]] = new_value
            applied_submission_repairs.append(
                {"row": row_index, "old": old_value, "new": new_value}
            )
        for start, end in blank_runs(candidate, expected_end):
            if start == 0 or end + 1 >= expected_end:
                skipped.append(
                    {"row": row_index, "start": start, "end": end, "reason": "edge"}
                )
                continue
            left = normalize(candidate[start - 1])
            right = normalize(candidate[end + 1])
            length = end - start + 1
            matches = [
                index
                for index in range(len(old_values) - length - 1)
                if old_values[index] == left
                and old_values[index + length + 1] == right
            ]
            if len(matches) != 1:
                skipped.append(
                    {
                        "row": row_index,
                        "start": start,
                        "end": end,
                        "reason": "anchor_matches",
                        "matches": matches,
                        "left": left,
                        "right": right,
                        "candidate_context": candidate[
                            max(0, start - 3) : min(len(candidate), end + 4)
                        ],
                        "old_values": old_values,
                    }
                )
                continue
            old_start = matches[0] + 1
            values = old_values[old_start : old_start + length]
            if any(not re.fullmatch(r"[0-9]+\.[0-9]{2}", value) for value in values):
                skipped.append(
                    {
                        "row": row_index,
                        "start": start,
                        "end": end,
                        "reason": "non_numeric",
                        "values": values,
                    }
                )
                continue
            numeric_chain = [left, *values, right]
            if any(
                not re.fullmatch(r"[0-9]+\.[0-9]{2}", value)
                for value in numeric_chain
            ):
                skipped.append(
                    {
                        "row": row_index,
                        "start": start,
                        "end": end,
                        "reason": "non_numeric_anchor",
                        "values": numeric_chain,
                    }
                )
                continue
            numeric_values = [float(value) for value in numeric_chain]
            if any(
                following <= preceding
                for preceding, following in zip(numeric_values, numeric_values[1:])
            ):
                skipped.append(
                    {
                        "row": row_index,
                        "start": start,
                        "end": end,
                        "reason": "non_monotonic",
                        "values": numeric_chain,
                    }
                )
                continue
            for offset, value in enumerate(values):
                candidate[start + offset] = value
                recovered.append(
                    {"row": row_index, "column": start + offset, "value": value}
                )

    report = {
        "image_name": args.image_name,
        "candidate": str(args.candidate),
        "submission": str(args.submission),
        "candidate_repairs": candidate_repairs,
        "submission_repairs": applied_submission_repairs,
        "recovered": len(recovered),
        "recovered_cells": recovered,
        "skipped_runs": skipped,
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if len(recovered) != args.expected_recovered:
        raise ValueError(
            f"expected {args.expected_recovered} recovered cells, "
            f"found {len(recovered)}; skipped={skipped}"
        )

    row_pattern = re.compile(r"^(?P<indent>[ \t]*)<tr>.*?</tr>$", re.M)
    row_matches = list(row_pattern.finditer(candidate_markdown))
    replacements: list[tuple[int, int, str]] = []
    for index, (match, row) in enumerate(zip(row_matches, candidate_rows)):
        rendered = match.group("indent") + "<tr>" + "".join(
            f"<td>{html.escape(value)}</td>" for value in row
        ) + "</tr>"
        replacements.append((match.start(), match.end(), rendered))
    result = candidate_markdown
    for start, end, rendered in reversed(replacements):
        result = result[:start] + rendered + result[end:]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"recovered": len(recovered), "skipped_runs": skipped}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
