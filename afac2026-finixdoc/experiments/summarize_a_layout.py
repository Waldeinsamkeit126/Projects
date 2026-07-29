from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.local_table_ocr import core_tiles  # noqa: E402
from afac2026.table_grid import analyze_table_layout  # noqa: E402


WANTED = {
    "b1044f0e-008d-45d4-8238-29910bafc7a5",
    "e082df7b-7afb-44ba-bf46-2c28ebe6c460",
    "d14d1076-a83f-4e0e-a912-fa67ac7403ae",
}
dataset = DatasetLayout.discover(Path(r"D:\AFAC2026\data"))
report = []
for image in dataset.test_images:
    if image.stem not in WANTED:
        continue
    layout = analyze_table_layout(image)
    report.append(
        {
            "image": str(image),
            "width": layout.width,
            "height": layout.height,
            "regions": [
                {
                    "rows": len(region.row_intervals),
                    "columns": len(region.column_intervals),
                    "cells": len(region.row_intervals) * len(region.column_intervals),
                    "tiles": len(core_tiles(region)),
                    "row_chunk": region.row_chunk_size,
                    "column_chunk": region.column_chunk_size,
                }
                for region in layout.regions
            ],
        }
    )
print(json.dumps(report, ensure_ascii=False, indent=2))
