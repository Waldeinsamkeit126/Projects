from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import cv2
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.table_grid import analyze_table_layout  # noqa: E402
from afac2026.table_tiles import _bounds  # noqa: E402


class Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def runs(active: np.ndarray) -> list[tuple[int, int]]:
    indexes = np.flatnonzero(active)
    if indexes.size == 0:
        return []
    result: list[tuple[int, int]] = []
    start = previous = int(indexes[0])
    for raw in indexes[1:]:
        value = int(raw)
        if value > previous + 1:
            result.append((start, previous + 1))
            start = value
        previous = value
    result.append((start, previous + 1))
    return result


def glyphs(array: np.ndarray, threshold: int = 220) -> list[np.ndarray]:
    mask = (array < threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components: list[tuple[int, np.ndarray]] = []
    for label in range(1, count):
        left, top, width, height, area = (int(value) for value in stats[label])
        if area <= 0:
            continue
        piece = np.full((height, width), 255, dtype=np.uint8)
        component_mask = labels[top : top + height, left : left + width] == label
        source = array[top : top + height, left : left + width]
        piece[component_mask] = source[component_mask]
        components.append((left, piece))
    return [piece for _, piece in sorted(components, key=lambda item: item[0])]


def normalized(piece: np.ndarray, size: tuple[int, int] = (16, 24)) -> np.ndarray:
    image = Image.fromarray(piece).resize(size, Image.Resampling.BILINEAR)
    return (255 - np.asarray(image, dtype=np.float32)) / 255.0


def cell_array(
    gray: np.ndarray,
    row_interval: tuple[int, int],
    columns: tuple[tuple[int, int], ...],
    column: int,
    width: int,
) -> np.ndarray:
    left, right = _bounds(columns, column, column + 1, 0, width)
    top, bottom = row_interval
    return gray[top:bottom, left:right]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("--train-region", type=int, default=0)
    parser.add_argument("--test-region", type=int, default=3)
    args = parser.parse_args()

    layout = analyze_table_layout(args.image)
    parsed = Tables()
    parsed.feed(args.ground_truth.read_text(encoding="utf-8"))
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(args.image) as source:
            gray = np.asarray(source.convert("L"))
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit

    allowed = set("0123456789.,-%")
    samples: dict[str, list[np.ndarray]] = defaultdict(list)
    train_region = layout.regions[args.train_region]
    train_truth = parsed.tables[args.train_region]
    aligned_cells = 0
    for row in range(1, min(len(train_region.row_intervals), len(train_truth))):
        for column in range(min(len(train_region.column_intervals), len(train_truth[row]))):
            expected = train_truth[row][column]
            if not expected or not set(expected) <= allowed:
                continue
            pieces = glyphs(
                cell_array(
                    gray,
                    train_region.row_intervals[row],
                    train_region.column_intervals,
                    column,
                    layout.width,
                )
            )
            if len(pieces) != len(expected):
                continue
            aligned_cells += 1
            for character, piece in zip(expected, pieces):
                samples[character].append(normalized(piece))

    templates = {
        character: np.median(np.stack(values), axis=0)
        for character, values in samples.items()
        if len(values) >= 3
    }
    test_region = layout.regions[args.test_region]
    test_truth = parsed.tables[args.test_region]
    total = exact = segmentable = 0
    differences: list[list[object]] = []
    for row in range(1, min(len(test_region.row_intervals), len(test_truth))):
        for column in range(min(len(test_region.column_intervals), len(test_truth[row]))):
            expected = test_truth[row][column]
            if not expected or not set(expected) <= allowed:
                continue
            total += 1
            pieces = glyphs(
                cell_array(
                    gray,
                    test_region.row_intervals[row],
                    test_region.column_intervals,
                    column,
                    layout.width,
                )
            )
            if len(pieces) != len(expected) or not templates:
                if len(differences) < 30:
                    differences.append([row, column, "<segmentation>", expected, len(pieces)])
                continue
            segmentable += 1
            predicted = "".join(
                min(
                    templates,
                    key=lambda character: float(
                        np.mean((normalized(piece) - templates[character]) ** 2)
                    ),
                )
                for piece in pieces
            )
            if predicted == expected:
                exact += 1
            elif len(differences) < 30:
                differences.append([row, column, predicted, expected, len(pieces)])

    print(
        json.dumps(
            {
                "train_aligned_cells": aligned_cells,
                "sample_counts": {key: len(value) for key, value in sorted(samples.items())},
                "test_cells": total,
                "segmentable": segmentable,
                "exact": exact,
                "accuracy_all": round(exact / max(total, 1), 6),
                "accuracy_segmentable": round(exact / max(segmentable, 1), 6),
                "difference_preview": differences,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
