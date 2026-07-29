from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402


CANDIDATES = {
    "4752c7d7-df43-48fc-8e1c-b15b57a76a51.jpg": "corner4_rule103_A_4752c7d7.md",
    "b8c1ae8f-9938-46a4-9ee9-1f7e7ea63d77.jpg": "corner4_rule103_A_b8c1ae8f.md",
}


def parse(markdown: str) -> tuple[_TableParser, list[str]]:
    parsed = _TableParser()
    parsed.feed(markdown)
    cells = [
        normalized_for_alignment(cell)
        for row in parsed.cell_text_rows
        for cell in row
    ]
    return parsed, cells


def summarize(markdown: str) -> dict[str, object]:
    parsed, cells = parse(markdown)
    lengths = list(map(len, parsed.cell_text_rows))
    return {
        "tables": parsed.tables,
        "rows": len(parsed.rows),
        "row_lengths": sorted(set(lengths)),
        "first_row_lengths": lengths[:3],
        "cells": len(cells),
        "nonempty_cells": sum(bool(cell) for cell in cells),
        "normalized_cell_characters": sum(map(len, cells)),
        "header_rows": parsed.cell_text_rows[:2],
    }


def agreement(left: str, right: str) -> dict[str, object]:
    _, left_cells = parse(left)
    _, right_cells = parse(right)
    left_nonempty = [cell for cell in left_cells if cell]
    right_nonempty = [cell for cell in right_cells if cell]
    matcher = difflib.SequenceMatcher(
        None, left_nonempty, right_nonempty, autojunk=False
    )
    exact = sum(block.size for block in matcher.get_matching_blocks())
    return {
        "candidate_nonempty_cells": len(left_nonempty),
        "current_nonempty_cells": len(right_nonempty),
        "ordered_exact_cells": exact,
        "candidate_coverage": round(exact / max(1, len(left_nonempty)), 6),
        "current_coverage": round(exact / max(1, len(right_nonempty)), 6),
        "sequence_ratio": round(matcher.ratio(), 6),
    }


def structure_ok(markdown: str, rows: int = 265, columns: int = 103) -> bool:
    parsed, _ = parse(markdown)
    lengths = list(map(len, parsed.rows))
    expected_lengths = [5, columns - 4, *([columns] * (rows - 2))]
    first = parsed.rows[0] if parsed.rows else []
    expected_first = [
        ("td", "2", None),
        ("td", "2", None),
        ("td", "2", None),
        ("td", "2", None),
        ("td", None, str(columns - 4)),
    ]
    return (
        parsed.tables == 1
        and lengths == expected_lengths
        and first == expected_first
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/corner4_A_candidate_audit.json"),
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        help="Override the default outputs/experiments candidate directory.",
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    experiment_dir = args.candidate_dir or settings.output_dir / "experiments"
    prediction_dir = settings.output_dir / "predictions_A"
    items: list[dict[str, object]] = []
    for name, candidate_name in CANDIDATES.items():
        candidate_path = experiment_dir / candidate_name
        if not candidate_path.is_file():
            continue
        current_path = prediction_dir / f"{Path(name).stem}.md"
        candidate = candidate_path.read_text(encoding="utf-8")
        current = current_path.read_text(encoding="utf-8")
        item = {
            "file_name": name,
            "candidate": str(candidate_path),
            "structure_ok": structure_ok(candidate),
            "candidate_summary": summarize(candidate),
            "current_summary": summarize(current),
            "candidate_to_current": agreement(candidate, current),
        }
        items.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    report = {
        "items": items,
        "all_structures_ok": len(items) == 2
        and all(bool(item["structure_ok"]) for item in items),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
