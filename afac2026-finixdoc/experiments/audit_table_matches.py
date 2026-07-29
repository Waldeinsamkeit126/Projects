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
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402


def image_feature(path: Path, size: int = 512) -> np.ndarray:
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path) as source:
            source.draft("L", (size, size))
            gray = source.convert("L").resize((size, size), Image.Resampling.BOX)
            return np.asarray(gray, dtype=np.float32)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit


def cells(markdown: str) -> list[str]:
    parser = _TableParser()
    parser.feed(markdown)
    return [
        normalized_for_alignment(cell)
        for row in parser.cell_text_rows
        for cell in row
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matches",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_table_template_matches.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_table_match_audit.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    train_images = {path.name: path for path in data.train_images}
    test_images = {path.name: path for path in data.test_images}
    gt_by_stem = {path.stem: path for path in data.train_markdowns}
    matches = json.loads(args.matches.read_text(encoding="utf-8"))
    items = []
    for record in matches["items"]:
        if float(record["matches"][0]["distance"]) > 0.05:
            continue
        test_name = str(record["file_name"])
        train_name = str(record["matches"][0]["file_name"])
        test_image = test_images[test_name]
        train_image = train_images[train_name]
        current = (
            settings.output_dir / "predictions_A" / f"{test_image.stem}.md"
        ).read_text(encoding="utf-8")
        gt = gt_by_stem[train_image.stem].read_text(encoding="utf-8")
        current_cells = cells(current)
        gt_cells = cells(gt)
        feature_test = image_feature(test_image)
        feature_train = image_feature(train_image)
        mae = float(np.mean(np.abs(feature_test - feature_train)))
        correlation = float(
            np.corrcoef(feature_test.ravel(), feature_train.ravel())[0, 1]
        )
        comparable = min(len(current_cells), len(gt_cells), 5000)
        item: dict[str, object] = {
            "file_name": test_name,
            "train_file": train_name,
            "template_distance": record["matches"][0]["distance"],
            "distance_ratio": record["distance_ratio"],
            "image_mae_512": round(mae, 6),
            "image_correlation_512": round(correlation, 6),
            "current_prefix_cells_compared": comparable,
            "current_prefix_exact_rate": round(
                sum(
                    left == right
                    for left, right in zip(
                        current_cells[:comparable], gt_cells[:comparable]
                    )
                )
                / max(comparable, 1),
                6,
            ),
            "current_cells": len(current_cells),
            "gt_cells": len(gt_cells),
            "current_shape_exact": record["best_shape_exact"],
        }
        backup = (
            settings.output_dir
            / "repair_backups"
            / test_image.stem
            / f"{test_image.stem}.md"
        )
        if backup.is_file():
            backup_cells = cells(backup.read_text(encoding="utf-8"))
            comparable = min(len(backup_cells), len(gt_cells))
            item.update(
                {
                    "api_backup_cells": len(backup_cells),
                    "api_prefix_exact_rate": round(
                        sum(
                            left == right
                            for left, right in zip(
                                backup_cells[:comparable], gt_cells[:comparable]
                            )
                        )
                        / max(comparable, 1),
                        6,
                    ),
                }
            )
        items.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    report = {"items": items}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
