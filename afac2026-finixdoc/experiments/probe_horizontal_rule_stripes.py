from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_name")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-width", type=int, default=6000)
    parser.add_argument("--minimum-lines", type=int, default=250)
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    images = {
        path.name: path for path in [*data.train_images, *data.test_images]
    }
    path = images[args.image_name]
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path) as source:
            width, height = source.size
            scale = min(1.0, args.max_width / width)
            target = (round(width * scale), round(height * scale))
            gray = source.convert("L")
            if gray.size != target:
                gray = gray.resize(target, Image.Resampling.BOX)
            array = np.asarray(gray)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    broad_mask = array < 220
    ink_columns = np.flatnonzero(
        broad_mask.sum(axis=0) > max(3, broad_mask.shape[0] // 2500)
    )
    content_left = int(ink_columns[0]) if ink_columns.size else 0
    content_right = (
        int(ink_columns[-1]) + 1 if ink_columns.size else broad_mask.shape[1]
    )
    content_width = max(1, content_right - content_left)
    results: list[dict[str, object]] = []
    for fraction in (0.03, 0.10, 0.25, 0.50, 0.75, 0.90, 0.97):
        center = content_left + round(content_width * fraction)
        for stripe_fraction in (0.01, 0.02, 0.04):
            half = max(3, round(content_width * stripe_fraction / 2))
            left = max(content_left, center - half)
            right = min(content_right, center + half + 1)
            for darkness in (120, 140, 160, 180, 200, 220):
                mask = array[:, left:right] < darkness
                for coverage in (0.70, 0.80, 0.90, 0.95):
                    active = np.flatnonzero(
                        mask.sum(axis=1) >= mask.shape[1] * coverage
                    )
                    centers = _thin_line_centers(active, maximum_thickness=8)
                    groups = _line_groups(centers)
                    for group in groups:
                        if len(group) < args.minimum_lines:
                            continue
                        gaps = np.diff(np.asarray(group))
                        results.append(
                            {
                                "fraction": fraction,
                                "stripe_fraction": stripe_fraction,
                                "darkness": darkness,
                                "coverage": coverage,
                                "lines": len(group),
                                "first": group[0] / scale,
                                "last": group[-1] / scale,
                                "median_gap": float(np.median(gaps)) / scale,
                                "minimum_gap": float(np.min(gaps)) / scale,
                                "maximum_gap": float(np.max(gaps)) / scale,
                                "centers": [value / scale for value in group],
                            }
                        )
    frequencies = Counter(int(item["lines"]) for item in results)
    report = {
        "file_name": args.image_name,
        "image": str(path),
        "scale": scale,
        "content_left": content_left / scale,
        "content_right": content_right / scale,
        "frequencies": frequencies.most_common(),
        "results": results,
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "results"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
