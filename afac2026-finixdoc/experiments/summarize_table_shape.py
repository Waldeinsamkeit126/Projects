from __future__ import annotations

import argparse
import json
import sys
from itertools import groupby

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown_name")
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    markdowns = {path.name: path for path in data.train_markdowns}
    parsed = _TableParser()
    parsed.feed(markdowns[args.markdown_name].read_text(encoding="utf-8"))
    lengths = [len(row) for row in parsed.rows]
    runs = [
        {"length": length, "rows": len(list(items))}
        for length, items in groupby(lengths)
    ]
    signatures = [
        [
            {"tag": tag, "rowspan": rowspan, "colspan": colspan}
            for tag, rowspan, colspan in row
        ]
        for row in parsed.rows
        if len(row) != max(lengths)
    ]
    print(
        json.dumps(
            {
                "tables": parsed.tables,
                "rows": len(parsed.rows),
                "cells": sum(lengths),
                "row_length_runs": runs,
                "non_full_row_signatures": signatures,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
