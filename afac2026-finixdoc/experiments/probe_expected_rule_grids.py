from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.constrained_table_ocr import _rule_grid_boundaries  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402


def parse_shape(value: str) -> tuple[int, int]:
    parts = value.lower().split("x", 1)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"shape must be ROWSxCOLUMNS: {value!r}")
    rows, columns = map(int, parts)
    if rows < 1 or columns < 1:
        raise argparse.ArgumentTypeError(f"invalid shape: {value!r}")
    return rows, columns


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_name")
    parser.add_argument("--image-path", type=Path)
    parser.add_argument("--shape", type=parse_shape, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    images = {
        path.name: path for path in [*data.train_images, *data.test_images]
    }
    image = args.image_path or images[args.image_name]
    configurations = list(
        product(
            (3000, 6000),
            (160, 180, 200, 220, 235),
            (0.35, 0.50, 0.65, 0.75),
            (0.60, 0.70, 0.80),
        )
    )
    items: list[dict[str, object]] = []
    for rows, columns in args.shape:
        successes: list[dict[str, object]] = []
        failures: Counter[str] = Counter()
        for max_width, darkness, horizontal, vertical in configurations:
            try:
                horizontal_rules, vertical_rules = _rule_grid_boundaries(
                    image,
                    rows,
                    columns,
                    max_width=max_width,
                    darkness=darkness,
                    horizontal_coverage=horizontal,
                    vertical_coverage=vertical,
                )
            except ValueError as error:
                failures[str(error)] += 1
                continue
            successes.append(
                {
                    "max_width": max_width,
                    "darkness": darkness,
                    "horizontal_coverage": horizontal,
                    "vertical_coverage": vertical,
                    "horizontal_rules": len(horizontal_rules),
                    "vertical_rules": len(vertical_rules),
                    "top": horizontal_rules[0],
                    "bottom": horizontal_rules[-1],
                }
            )
        item = {
            "shape": [rows, columns],
            "configurations": len(configurations),
            "successes": len(successes),
            "success_rate": len(successes) / len(configurations),
            "successful_configurations": successes,
            "failure_frequencies": failures.most_common(),
        }
        items.append(item)
        print(
            json.dumps(
                {key: value for key, value in item.items() if key != "successful_configurations"},
                ensure_ascii=False,
            ),
            flush=True,
        )
    report = {
        "image_name": args.image_name,
        "image": str(image),
        "items": items,
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
