from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.constrained_table_ocr import _rule_grid_boundaries  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.table_grid import _runs  # noqa: E402
from afac2026.config import Settings  # noqa: E402


SPECS = {
    "e082df7b-7afb-44ba-bf46-2c28ebe6c460.jpg": (355, 112),
    "4752c7d7-df43-48fc-8e1c-b15b57a76a51.jpg": (265, 90),
    "b8c1ae8f-9938-46a4-9ee9-1f7e7ea63d77.jpg": (265, 90),
    "aecf66d9-d361-4b7b-948a-e5e8693c4877.jpg": (325, 96),
    "bf21c4c0-cab4-4116-9b64-fe341dad80e1.jpg": (304, 98),
    "bac0aeac-2cea-49c3-8714-d8f8753afcde.jpg": (314, 101),
}


def centers(active: np.ndarray, maximum_thickness: int = 8) -> list[float]:
    return [
        (left + right) / 2
        for left, right in _runs(active, max_internal_gap=1)
        if right - left + 1 <= maximum_thickness
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("work_header_grid_columns.json")
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    images = {path.name: path for path in data.test_images}
    items = []
    for name, (rows, detected_columns) in SPECS.items():
        path = images[name]
        boundary_options = (
            {
                "max_width": 6000,
                "darkness": 220,
                "horizontal_coverage": 0.50,
            }
            if name == "e082df7b-7afb-44ba-bf46-2c28ebe6c460.jpg"
            else {}
        )
        horizontal, _ = _rule_grid_boundaries(
            path, rows, detected_columns, **boundary_options
        )
        old_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            with Image.open(path) as source:
                array = np.asarray(source.convert("L"))
        finally:
            Image.MAX_IMAGE_PIXELS = old_limit
        results = []
        bands = {
            "header_first": (horizontal[0], horizontal[1]),
            "header_second": (horizontal[1], horizontal[2]),
            "first_5_rows": (horizontal[1], horizontal[6]),
            "first_20_rows": (horizontal[1], horizontal[21]),
            "whole_grid": (horizontal[0], horizontal[-1]),
        }
        for band, (raw_top, raw_bottom) in bands.items():
            top = max(0, round(raw_top) + 2)
            bottom = min(array.shape[0], round(raw_bottom) - 1)
            region = array[top:bottom]
            for darkness in (160, 180, 200, 220, 235):
                mask = region < darkness
                for coverage in (0.50, 0.65, 0.75, 0.85):
                    active = np.flatnonzero(
                        mask.sum(axis=0) >= max(1, region.shape[0] * coverage)
                    )
                    values = centers(active)
                    results.append(
                        {
                            "band": band,
                            "darkness": darkness,
                            "coverage": coverage,
                            "lines": len(values),
                            "columns": max(0, len(values) - 1),
                            "centers": values if 95 <= len(values) <= 110 else None,
                        }
                    )
        near = [result for result in results if 95 <= int(result["lines"]) <= 115]
        item = {"file_name": name, "near_target_lines": near, "results": results}
        items.append(item)
        print(
            json.dumps(
                {"file_name": name, "near_target_lines": near}, ensure_ascii=False
            ),
            flush=True,
        )
    report = {"items": items}
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
