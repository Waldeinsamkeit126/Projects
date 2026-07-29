from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.table_grid import _runs  # noqa: E402


def expected_shapes(markdown: str) -> list[tuple[int, int]]:
    result = []
    for match in re.finditer(r"<table\b.*?</table>", markdown, flags=re.I | re.S):
        parsed = _TableParser()
        parsed.feed(match.group(0))
        columns = max(
            (
                sum(int(colspan or 1) for _, _, colspan in row)
                for row in parsed.rows
            ),
            default=0,
        )
        result.append((len(parsed.rows), columns))
    return result


def _centers(active: np.ndarray, maximum_thickness: int = 12) -> list[float]:
    return [
        (start + end) / 2
        for start, end in _runs(active, max_internal_gap=1)
        if end - start + 1 <= maximum_thickness
    ]


def _line_groups(centers: list[float]) -> list[list[float]]:
    if len(centers) < 3:
        return []
    gaps = np.diff(np.asarray(centers, dtype=np.float32))
    lower = gaps[gaps <= np.percentile(gaps, 60)]
    typical = float(np.median(lower)) if lower.size else float(np.median(gaps))
    split_gap = max(18.0, typical * 4.5)
    groups: list[list[float]] = [[centers[0]]]
    for center in centers[1:]:
        if center - groups[-1][-1] > split_gap:
            groups.append([center])
        else:
            groups[-1].append(center)
    return [group for group in groups if len(group) >= 3]


def detect_shapes(
    image_path: Path,
    max_width: int = 3000,
    darkness: int = 200,
    horizontal_coverage: float = 0.35,
    vertical_coverage: float = 0.70,
) -> tuple[list[tuple[int, int]], dict[str, object]]:
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as source:
            width, height = source.size
            scale = min(1.0, max_width / max(width, 1))
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            gray = source.convert("L")
            if gray.size != target:
                gray = gray.resize(target, Image.Resampling.BOX)
            array = np.asarray(gray)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit

    mask = array < darkness
    analysis_height, analysis_width = mask.shape
    ink_columns = np.flatnonzero(
        mask.sum(axis=0) > max(3, analysis_height // 2500)
    )
    if ink_columns.size:
        content_left = int(ink_columns[0])
        content_right = int(ink_columns[-1]) + 1
    else:
        content_left, content_right = 0, analysis_width
    content_width = max(1, content_right - content_left)
    horizontal_active = np.flatnonzero(
        mask[:, content_left:content_right].sum(axis=1)
        >= content_width * horizontal_coverage
    )
    horizontal_centers = _centers(horizontal_active)
    groups = _line_groups(horizontal_centers)
    shapes = []
    details = []
    for group in groups:
        top = max(0, round(group[0]))
        bottom = min(analysis_height, round(group[-1]) + 1)
        region_height = max(1, bottom - top)
        vertical_active = np.flatnonzero(
            mask[top:bottom, :].sum(axis=0)
            >= region_height * vertical_coverage
        )
        vertical_centers = _centers(vertical_active)
        if len(vertical_centers) < 2:
            continue
        shape = (len(group) - 1, len(vertical_centers) - 1)
        shapes.append(shape)
        details.append(
            {
                "top": round(group[0] / scale),
                "bottom": round(group[-1] / scale),
                "horizontal_lines": len(group),
                "vertical_lines": len(vertical_centers),
                "shape": shape,
            }
        )
    return shapes, {
        "width": width,
        "height": height,
        "scale": scale,
        "horizontal_candidates": len(horizontal_centers),
        "groups": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", nargs="*")
    parser.add_argument(
        "--split", choices=("train", "test", "all"), default="train"
    )
    parser.add_argument("--max-width", type=int, default=3000)
    parser.add_argument("--darkness", type=int, default=200)
    parser.add_argument("--horizontal-coverage", type=float, default=0.35)
    parser.add_argument("--vertical-coverage", type=float, default=0.70)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/rule_grid_shape_audit.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    images = [*data.train_images, *data.test_images]
    if args.names:
        wanted = set(args.names)
        images = [image for image in images if image.name in wanted]
    else:
        if args.split == "train":
            images = list(data.train_images)
        elif args.split == "test":
            images = list(data.test_images)
        images = [image for image in images if "table" in str(image).lower()]

    items = []
    exact = 0
    for image in images:
        detected, details = detect_shapes(
            image,
            args.max_width,
            args.darkness,
            args.horizontal_coverage,
            args.vertical_coverage,
        )
        gt_path = None
        try:
            gt_path = data.gt_for(image)
        except (FileNotFoundError, KeyError):
            pass
        expected = (
            expected_shapes(gt_path.read_text(encoding="utf-8"))
            if gt_path is not None and gt_path.is_file()
            else None
        )
        is_exact = expected == detected if expected is not None else None
        exact += is_exact is True
        item = {
            "file_name": image.name,
            "expected": expected,
            "detected": detected,
            "exact": is_exact,
            **details,
        }
        items.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    report = {
        "images": len(items),
        "with_ground_truth": sum(item["expected"] is not None for item in items),
        "exact": exact,
        "parameters": {
            "split": args.split,
            "max_width": args.max_width,
            "darkness": args.darkness,
            "horizontal_coverage": args.horizontal_coverage,
            "vertical_coverage": args.vertical_coverage,
        },
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(json.dumps({key: value for key, value in report.items() if key != "items"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
