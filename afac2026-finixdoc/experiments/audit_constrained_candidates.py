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
    "d8b59365-8a47-4d71-8d6f-564f8084aac8.jpg": (
        "constrained_A_d8b59365.md",
        72,
        11,
        False,
    ),
    "4c9e11b2-a594-472b-8658-1b88e2fdeaaf.jpg": (
        "constrained_A_4c9e11b2.md",
        107,
        72,
        False,
    ),
    "dc98af1d-ad8e-4418-baf1-ab775b5b0843.jpg": (
        "constrained_A_dc98af1d.md",
        106,
        72,
        False,
    ),
    "f353d76e-efd7-4a3c-8579-38b3f916a6d3.jpg": (
        "constrained_A_f353d76e.md",
        106,
        72,
        False,
    ),
    "58b3cb9e-ef05-45c4-875d-39dd34ea9dbe.jpg": (
        "constrained_A_58b3cb9e.md",
        107,
        37,
        False,
    ),
    "f3cfab65-77d7-4c72-8f40-b4bc14624f52.jpg": (
        "corner_A_f3cfab65.md",
        107,
        72,
        True,
    ),
    "8e60d5f8-1462-4d57-bcfa-3cc5c3a82d2a.jpg": (
        "corner_A_8e60d5f8.md",
        107,
        72,
        True,
    ),
    "6dfcd28f-b67a-49de-86ee-3c79a5077351.jpg": (
        "corner_A_6dfcd28f.md",
        90,
        57,
        True,
    ),
    "d14d1076-a83f-4e0e-a912-fa67ac7403ae.jpg": (
        "corner_A_d14d1076.md",
        90,
        57,
        True,
    ),
}


def parse(markdown: str) -> tuple[_TableParser, list[str], list[str]]:
    parser = _TableParser()
    parser.feed(markdown)
    cells = [
        normalized_for_alignment(cell)
        for row in parser.cell_text_rows
        for cell in row
    ]
    return parser, cells, [cell for cell in cells if cell]


def summary(markdown: str) -> dict[str, object]:
    parser, cells, nonempty = parse(markdown)
    lengths = list(map(len, parser.cell_text_rows))
    return {
        "tables": parser.tables,
        "rows": len(parser.cell_text_rows),
        "row_lengths": sorted(set(lengths)),
        "first_row_lengths": lengths[:3],
        "cells": len(cells),
        "nonempty_cells": len(nonempty),
        "normalized_cell_characters": sum(map(len, cells)),
    }


def sequence_agreement(left_markdown: str, right_markdown: str) -> dict[str, object]:
    _, _, left = parse(left_markdown)
    _, _, right = parse(right_markdown)
    matcher = difflib.SequenceMatcher(None, left, right)
    exact = sum(block.size for block in matcher.get_matching_blocks())
    return {
        "left_nonempty_cells": len(left),
        "right_nonempty_cells": len(right),
        "ordered_exact_cells": exact,
        "left_coverage": round(exact / max(len(left), 1), 6),
        "right_coverage": round(exact / max(len(right), 1), 6),
        "sequence_ratio": round(matcher.ratio(), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/constrained_A_candidate_audit.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    experiment_dir = settings.output_dir / "experiments"
    items = []
    for name, (
        experiment_name,
        expected_rows,
        expected_columns,
        corner_header_span,
    ) in CANDIDATES.items():
        experiment_path = experiment_dir / experiment_name
        if not experiment_path.is_file():
            continue
        stem = Path(name).stem
        current_path = settings.output_dir / "predictions_A" / f"{stem}.md"
        backup_path = settings.output_dir / "repair_backups" / stem / f"{stem}.md"
        experiment = experiment_path.read_text(encoding="utf-8")
        current = current_path.read_text(encoding="utf-8")
        experiment_summary = summary(experiment)
        if corner_header_span:
            expected_length_set = sorted(
                {2, expected_columns - 1, expected_columns}
            )
            expected_first = [2, expected_columns - 1, expected_columns]
        else:
            expected_length_set = [expected_columns]
            expected_first = [expected_columns] * min(3, expected_rows)
        structure_ok = (
            experiment_summary["tables"] == 1
            and experiment_summary["rows"] == expected_rows
            and experiment_summary["row_lengths"] == expected_length_set
            and experiment_summary["first_row_lengths"] == expected_first
        )
        item: dict[str, object] = {
            "file_name": name,
            "experiment": str(experiment_path),
            "expected_rows": expected_rows,
            "expected_columns": expected_columns,
            "corner_header_span": corner_header_span,
            "structure_ok": structure_ok,
            "experiment_summary": experiment_summary,
            "current_summary": summary(current),
            "experiment_to_current": sequence_agreement(experiment, current),
        }
        if backup_path.is_file():
            backup = backup_path.read_text(encoding="utf-8")
            item["api_backup_summary"] = summary(backup)
            item["experiment_to_api_backup"] = sequence_agreement(
                experiment, backup
            )
        items.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    report = {"items": items, "all_structures_ok": all(item["structure_ok"] for item in items)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
