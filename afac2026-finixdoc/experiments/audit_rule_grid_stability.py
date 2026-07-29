from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from audit_rule_grid_shapes import detect_shapes, expected_shapes  # noqa: E402


NAMES = (
    "1ae225a3-3ec1-403a-bff5-10a2cfabbe74.jpg",
    "e84bf0cc-819c-4f7f-8cfb-3fa4b45265fc.jpg",
    "4752c7d7-df43-48fc-8e1c-b15b57a76a51.jpg",
    "b8c1ae8f-9938-46a4-9ee9-1f7e7ea63d77.jpg",
)


def shape_key(shapes: list[tuple[int, int]]) -> str:
    return ",".join(f"{rows}x{columns}" for rows, columns in shapes) or "none"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("work_rule_grid_stability.json")
    )
    parser.add_argument("--names", nargs="*")
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    images = {
        path.name: path for path in [*data.train_images, *data.test_images]
    }
    gt_by_stem = {path.stem: path for path in data.train_markdowns}
    configurations = list(
        product((180, 200, 220), (0.30, 0.35, 0.40), (0.65, 0.70))
    )

    items: list[dict[str, object]] = []
    for name in args.names or NAMES:
        image = images[name]
        results = []
        counter: Counter[str] = Counter()
        for darkness, horizontal, vertical in configurations:
            shapes, _ = detect_shapes(
                image,
                max_width=3000,
                darkness=darkness,
                horizontal_coverage=horizontal,
                vertical_coverage=vertical,
            )
            key = shape_key(shapes)
            counter[key] += 1
            results.append(
                {
                    "darkness": darkness,
                    "horizontal_coverage": horizontal,
                    "vertical_coverage": vertical,
                    "shape": key,
                }
            )
        gt_path = gt_by_stem.get(image.stem)
        expected = (
            shape_key(expected_shapes(gt_path.read_text(encoding="utf-8")))
            if gt_path is not None
            else None
        )
        mode, mode_count = counter.most_common(1)[0]
        item = {
            "file_name": name,
            "expected": expected,
            "configurations": len(configurations),
            "mode": mode,
            "mode_count": mode_count,
            "mode_rate": round(mode_count / len(configurations), 6),
            "expected_count": counter[expected] if expected is not None else None,
            "frequencies": dict(counter.most_common()),
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
    report = {"configurations": len(configurations), "items": items}
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
