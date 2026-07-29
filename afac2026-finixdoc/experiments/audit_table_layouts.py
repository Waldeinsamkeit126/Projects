from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.local_table_ocr import (  # noqa: E402
    local_layout_stats,
    prefer_content_relative_layout,
)
from afac2026.table_grid import analyze_table_layout  # noqa: E402


started = time.perf_counter()
dataset = DatasetLayout.discover(Path(r"D:\AFAC2026\data"))
records = []
for image in dataset.train_images:
    if "table" not in str(image).lower():
        continue
    ground_truth = dataset.gt_for(image).read_text(encoding="utf-8")
    expected_tables = len(re.findall(r"<table\b", ground_truth, flags=re.I))
    page_layout = analyze_table_layout(image, content_relative_rules=False)
    page_stats = local_layout_stats(page_layout)
    layout = page_layout
    stats = page_stats
    scope = "page"
    content_region_count = None
    if not page_stats["suitable"]:
        content_layout = analyze_table_layout(image, content_relative_rules=True)
        content_stats = local_layout_stats(content_layout)
        content_region_count = len(content_layout.regions)
        if prefer_content_relative_layout(page_stats, content_stats):
            layout = content_layout
            stats = content_stats
            scope = "content"
    records.append(
        {
            "file_name": image.name,
            "expected_tables": expected_tables,
            "page_detected_regions": len(page_layout.regions),
            "page_region_count_exact": expected_tables == len(page_layout.regions),
            "content_detected_regions": content_region_count,
            "detected_regions": len(layout.regions),
            "region_count_exact": expected_tables == len(layout.regions),
            "rule_scope": scope,
            "grid_cells": stats["total_cells"],
            "local_tiles": stats["tile_count"],
            "max_local_tile_pixels": stats["max_tile_pixels"],
            "local_suitable": stats["suitable"],
        }
    )

report = {
    "table_images": len(records),
    "region_count_exact": sum(record["region_count_exact"] for record in records),
    "page_region_count_exact": sum(
        record["page_region_count_exact"] for record in records
    ),
    "content_scope_selected": sum(
        record["rule_scope"] == "content" for record in records
    ),
    "mismatches": [record for record in records if not record["region_count_exact"]],
    "elapsed_seconds": round(time.perf_counter() - started, 3),
    "records": records,
}
destination = Path(r"D:\AFAC2026\outputs\training_table_layout_audit_v2.json")
destination.parent.mkdir(parents=True, exist_ok=True)
temporary = destination.with_suffix(".json.tmp")
temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
temporary.replace(destination)
print(
    json.dumps(
        {
            "output": str(destination),
            "table_images": report["table_images"],
            "region_count_exact": report["region_count_exact"],
            "page_region_count_exact": report["page_region_count_exact"],
            "content_scope_selected": report["content_scope_selected"],
            "mismatch_count": len(report["mismatches"]),
            "elapsed_seconds": report["elapsed_seconds"],
        },
        ensure_ascii=False,
        indent=2,
    )
)
