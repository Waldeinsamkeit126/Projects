from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.score import _TableParser  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-leading-rows", type=int, default=1)
    parser.add_argument("--skip-leading-columns", type=int, default=4)
    args = parser.parse_args()

    parsed = _TableParser()
    parsed.feed(args.input.read_text(encoding="utf-8"))
    rows = parsed.cell_text_rows[args.skip_leading_rows :]
    items: list[dict[str, object]] = []
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            if column_index < args.skip_leading_columns or not value.strip():
                continue
            if re.fullmatch(r"[0-9\s,.:，。]+", value):
                continue
            items.append(
                {
                    "row": row_index,
                    "column": column_index,
                    "keys": row[:4],
                    "value": value,
                    "previous_same_column": (
                        rows[row_index - 1][column_index] if row_index else None
                    ),
                    "next_same_column": (
                        rows[row_index + 1][column_index]
                        if row_index + 1 < len(rows)
                        else None
                    ),
                    "row_window": row[max(0, column_index - 2) : column_index + 3],
                }
            )
    report = {"input": str(args.input), "count": len(items), "items": items}
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
