from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.normalize import normalized_for_alignment  # noqa: E402
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


def cells(markdown: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    matches = re.findall(r"<table[^>]*>.*?</table>", markdown, flags=re.I | re.S)
    for table_index, match in enumerate(matches):
        parsed = _TableParser()
        parsed.feed(match)
        for row_index, row in enumerate(parsed.cell_text_rows):
            for column_index, value in enumerate(row):
                normalized = normalized_for_alignment(value)
                if normalized:
                    result.append(
                        {
                            "table": table_index,
                            "row": row_index,
                            "column": column_index,
                            "value": value,
                            "normalized": normalized,
                        }
                    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_name")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = cells(args.candidate.read_text(encoding="utf-8"))
    old = cells(load_prediction(args.submission, args.image_name))
    candidate_values = [str(item["normalized"]) for item in candidate]
    old_values = [str(item["normalized"]) for item in old]
    matcher = difflib.SequenceMatcher(
        None, candidate_values, old_values, autojunk=False
    )
    disagreements: list[dict[str, object]] = []
    for tag, candidate_start, candidate_end, old_start, old_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        disagreements.append(
            {
                "tag": tag,
                "candidate": candidate[candidate_start:candidate_end],
                "old": old[old_start:old_end],
                "left_anchor": (
                    candidate[candidate_start - 1] if candidate_start else None
                ),
                "right_anchor": (
                    candidate[candidate_end]
                    if candidate_end < len(candidate)
                    else None
                ),
            }
        )
    report = {
        "image_name": args.image_name,
        "candidate_cells": len(candidate),
        "old_cells": len(old),
        "disagreement_blocks": len(disagreements),
        "disagreements": disagreements,
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "candidate_cells": len(candidate),
                "old_cells": len(old),
                "disagreement_blocks": len(disagreements),
                "block_lengths": [
                    [item["tag"], len(item["candidate"]), len(item["old"])]
                    for item in disagreements
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
