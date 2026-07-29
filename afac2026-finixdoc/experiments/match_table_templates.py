from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402


def is_table(path: Path) -> bool:
    return any("table" in part.lower() for part in path.parts)


def feature(path: Path, size: int = 192) -> np.ndarray:
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path) as source:
            source.draft("L", (size * 4, size * 4))
            gray = source.convert("L").resize((size, size), Image.Resampling.BOX)
            array = np.asarray(gray, dtype=np.float32) / 255.0
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    ink = 1.0 - array
    row = ink.mean(axis=1)
    column = ink.mean(axis=0)
    pooled = ink.reshape(32, size // 32, 32, size // 32).mean(axis=(1, 3))
    vector = np.concatenate((row * 3.0, column * 3.0, pooled.ravel()))
    norm = float(np.linalg.norm(vector))
    return vector / max(norm, 1e-8)


def table_shape(markdown: str) -> dict[str, object]:
    parser = _TableParser()
    parser.feed(markdown)
    rows_per_table: list[int] = []
    cells_per_table: list[int] = []
    current_rows = 0
    current_cells = 0

    # _TableParser stores flattened rows, so also collect per-table structure
    # with a tiny dedicated state machine.
    from html.parser import HTMLParser

    class ShapeParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.rows: list[int] = []
            self.cells: list[int] = []
            self._rows = 0
            self._cells = 0
            self._inside = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            del attrs
            tag = tag.lower()
            if tag == "table":
                self._inside = True
                self._rows = 0
                self._cells = 0
            elif self._inside and tag == "tr":
                self._rows += 1
            elif self._inside and tag in {"td", "th"}:
                self._cells += 1

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() == "table" and self._inside:
                self.rows.append(self._rows)
                self.cells.append(self._cells)
                self._inside = False

    shape = ShapeParser()
    shape.feed(markdown)
    rows_per_table.extend(shape.rows)
    cells_per_table.extend(shape.cells)
    current_rows += 0
    current_cells += 0
    return {
        "tables": len(rows_per_table),
        "rows": rows_per_table,
        "cells": cells_per_table,
        "total_rows": sum(rows_per_table),
        "total_cells": sum(cells_per_table),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_table_template_matches.json"),
    )
    parser.add_argument(
        "--submission",
        type=Path,
        help="Read predictions from a submission CSV instead of predictions_A/*.md.",
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    train = [path for path in data.train_images if is_table(path)]
    test = [path for path in data.test_images if is_table(path)]
    gt_by_stem = {path.stem: path for path in data.train_markdowns}
    train_features = np.stack([feature(path) for path in train])
    train_shapes = {
        path.stem: table_shape(gt_by_stem[path.stem].read_text(encoding="utf-8"))
        for path in train
    }
    submission: dict[str, str] | None = None
    if args.submission:
        csv.field_size_limit(1_000_000_000)
        with args.submission.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["file_name", "ground_truth"]:
                raise ValueError(f"unexpected submission columns: {reader.fieldnames}")
            submission = {
                str(row["file_name"]): str(row["ground_truth"]) for row in reader
            }
    results = []
    for index, path in enumerate(test, 1):
        vector = feature(path)
        distances = 1.0 - train_features @ vector
        order = np.argsort(distances)[:3]
        if submission is None:
            prediction = settings.output_dir / "predictions_A" / f"{path.stem}.md"
            prediction_text = prediction.read_text(encoding="utf-8")
        else:
            prediction_text = submission[path.name]
        predicted_shape = table_shape(prediction_text)
        matches = [
            {
                "file_name": train[int(match)].name,
                "distance": round(float(distances[int(match)]), 6),
                "shape": train_shapes[train[int(match)].stem],
            }
            for match in order
        ]
        best_shape = matches[0]["shape"]
        results.append(
            {
                "file_name": path.name,
                "predicted_shape": predicted_shape,
                "matches": matches,
                "distance_ratio": round(
                    float(distances[int(order[0])])
                    / max(float(distances[int(order[1])]), 1e-9),
                    4,
                ),
                "best_shape_exact": predicted_shape == best_shape,
                "progress": f"{index}/{len(test)}",
            }
        )
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    report = {
        "submission": str(args.submission) if args.submission else None,
        "train_tables": len(train),
        "test_tables": len(test),
        "best_shape_exact": sum(item["best_shape_exact"] for item in results),
        "items": results,
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
