from __future__ import annotations

import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.image_plan import image_info  # noqa: E402


dataset = DatasetLayout.discover(Path(r"D:\AFAC2026\data"))
rows = []
for image in dataset.train_images:
    if "long" not in str(image).lower():
        continue
    info = image_info(image)
    chars = len(dataset.gt_for(image).read_text(encoding="utf-8"))
    rows.append({"image": image.name, "pixels": info.pixels, "chars": chars})

budgets = []
for limit in (30_000_000, 45_000_000, 55_000_000, 60_000_000):
    calls = sum(max(1, math.ceil(row["pixels"] / limit)) for row in rows)
    estimated_chunk_chars = [
        row["chars"] * min(1.0, limit / row["pixels"]) for row in rows
    ]
    budgets.append(
        {
            "pixel_limit": limit,
            "train_call_estimate": calls,
            "max_proportional_chunk_chars": round(max(estimated_chunk_chars), 1),
            "p95_proportional_chunk_chars": round(
                sorted(estimated_chunk_chars)[int(0.95 * (len(rows) - 1))], 1
            ),
        }
    )

print(
    json.dumps(
        {
            "documents": len(rows),
            "max_document_chars": max(row["chars"] for row in rows),
            "max_pixels": max(row["pixels"] for row in rows),
            "budgets": budgets,
        },
        ensure_ascii=False,
        indent=2,
    )
)
