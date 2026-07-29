from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402


def table_cells(markdown: str) -> list[str]:
    parser = _TableParser()
    parser.feed(markdown)
    return [
        normalized_for_alignment(cell)
        for row in parser.cell_text_rows
        for cell in row
    ]


def cell_alignment(left: list[str], right: list[str]) -> dict[str, object]:
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    blocks = [block for block in matcher.get_matching_blocks() if block.size]
    exact = sum(block.size for block in blocks)
    positional = sum(a == b for a, b in zip(left, right))
    return {
        "left_cells": len(left),
        "right_cells": len(right),
        "exact_cells_in_order": exact,
        "left_coverage": round(exact / max(len(left), 1), 6),
        "right_coverage": round(exact / max(len(right), 1), 6),
        "positional_exact": positional,
        "positional_rate": round(positional / max(min(len(left), len(right)), 1), 6),
        "longest_exact_run": max((block.size for block in blocks), default=0),
        "first_blocks": [
            {"left": block.a, "right": block.b, "size": block.size}
            for block in blocks[:10]
        ],
    }


def image_feature(path: Path, width: int = 2048) -> np.ndarray:
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path) as source:
            source.draft("L", (width, width))
            gray = ImageOps.grayscale(source)
            height = max(1, round(gray.height * width / max(gray.width, 1)))
            return np.asarray(
                gray.resize((width, height), Image.Resampling.BOX),
                dtype=np.float32,
            )
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit


def image_metrics(left_path: Path, right_path: Path) -> dict[str, object]:
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(left_path) as left, Image.open(right_path) as right:
            left_size = left.size
            right_size = right.size
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    left = image_feature(left_path)
    right = image_feature(right_path)
    common_height = min(left.shape[0], right.shape[0])
    if left.shape[0] != common_height:
        left = np.asarray(
            Image.fromarray(left.astype(np.uint8)).resize(
                (left.shape[1], common_height), Image.Resampling.BOX
            ),
            dtype=np.float32,
        )
    if right.shape[0] != common_height:
        right = np.asarray(
            Image.fromarray(right.astype(np.uint8)).resize(
                (right.shape[1], common_height), Image.Resampling.BOX
            ),
            dtype=np.float32,
        )
    difference = np.abs(left - right)
    return {
        "left_size": left_size,
        "right_size": right_size,
        "aspect_ratio_delta": round(
            abs(left_size[0] / left_size[1] - right_size[0] / right_size[1]), 9
        ),
        "mae_2048": round(float(difference.mean()), 6),
        "rmse_2048": round(float(np.sqrt(np.square(difference).mean())), 6),
        "correlation_2048": round(
            float(np.corrcoef(left.ravel(), right.ravel())[0, 1]), 6
        ),
        "pixels_delta_gt_8": round(float((difference > 8).mean()), 6),
        "pixels_delta_gt_24": round(float((difference > 24).mean()), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("test_name")
    parser.add_argument("train_name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    test_images = {path.name: path for path in data.test_images}
    train_images = {path.name: path for path in data.train_images}
    train_markdowns = {path.stem: path for path in data.train_markdowns}
    test_image = test_images[args.test_name]
    train_image = train_images[args.train_name]
    gt_path = train_markdowns[train_image.stem]
    current_path = settings.output_dir / "predictions_A" / f"{test_image.stem}.md"
    backup_path = (
        settings.output_dir
        / "repair_backups"
        / test_image.stem
        / f"{test_image.stem}.md"
    )

    gt_cells = table_cells(gt_path.read_text(encoding="utf-8"))
    current_cells = table_cells(current_path.read_text(encoding="utf-8"))
    result: dict[str, object] = {
        "test_name": args.test_name,
        "train_name": args.train_name,
        "image": image_metrics(test_image, train_image),
        "current_to_gt": cell_alignment(current_cells, gt_cells),
    }
    if backup_path.is_file():
        backup_cells = table_cells(backup_path.read_text(encoding="utf-8"))
        result["api_backup_to_gt"] = cell_alignment(backup_cells, gt_cells)
        result["api_backup_mismatches_at_same_position"] = [
            {"index": index, "api": left, "gt": right}
            for index, (left, right) in enumerate(zip(backup_cells, gt_cells))
            if left != right
        ][:20]

    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(output, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(output, encoding="utf-8")
        temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
