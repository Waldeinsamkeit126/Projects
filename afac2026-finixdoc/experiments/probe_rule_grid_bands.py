from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.constrained_table_ocr import (  # noqa: E402
    _line_groups,
    _thin_line_centers,
)
from afac2026.data import DatasetLayout  # noqa: E402


EXPECTED_ROWS = {
    "e082df7b-7afb-44ba-bf46-2c28ebe6c460.jpg": 355,
    "f5009a2d-b341-43f1-a9d3-d6f371606378.jpg": 262,
    "aecf66d9-d361-4b7b-948a-e5e8693c4877.jpg": 325,
    "bf21c4c0-cab4-4116-9b64-fe341dad80e1.jpg": 304,
    "bac0aeac-2cea-49c3-8714-d8f8753afcde.jpg": 314,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("work_rule_grid_bands.json")
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    images = {
        path.name: path for path in [*data.train_images, *data.test_images]
    }
    items = []
    for name, expected_rows in EXPECTED_ROWS.items():
        path = images[name]
        old_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            with Image.open(path) as source:
                width, height = source.size
                scale = min(1.0, 6000 / width)
                target = (round(width * scale), round(height * scale))
                gray = source.convert("L")
                if gray.size != target:
                    gray = gray.resize(target, Image.Resampling.BOX)
                array = np.asarray(gray)
        finally:
            Image.MAX_IMAGE_PIXELS = old_limit
        results = []
        for darkness in (160, 180, 200, 220, 235):
            mask = array < darkness
            ink_columns = np.flatnonzero(
                mask.sum(axis=0) > max(3, mask.shape[0] // 2500)
            )
            content_left = int(ink_columns[0]) if ink_columns.size else 0
            content_right = (
                int(ink_columns[-1]) + 1 if ink_columns.size else mask.shape[1]
            )
            content_width = max(1, content_right - content_left)
            for band_fraction in (0.03, 0.05, 0.08, 0.10, 0.15, 0.25, 1.0):
                right = min(
                    content_right,
                    content_left + max(5, round(content_width * band_fraction)),
                )
                region = mask[:, content_left:right]
                for coverage in (0.30, 0.50, 0.70, 0.85):
                    active = np.flatnonzero(
                        region.sum(axis=1) >= region.shape[1] * coverage
                    )
                    centers = _thin_line_centers(active)
                    groups = _line_groups(centers)
                    lengths = [len(group) for group in groups]
                    results.append(
                        {
                            "darkness": darkness,
                            "band_fraction": band_fraction,
                            "coverage": coverage,
                            "groups": lengths,
                            "exact": expected_rows + 1 in lengths,
                        }
                    )
        exact = [result for result in results if result["exact"]]
        item = {
            "file_name": name,
            "expected_horizontal_lines": expected_rows + 1,
            "exact_configurations": len(exact),
            "exact_results": exact,
            "results": results,
        }
        items.append(item)
        print(
            json.dumps(
                {key: value for key, value in item.items() if key != "results"},
                ensure_ascii=False,
            ),
            flush=True,
        )
    report = {"items": items}
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
