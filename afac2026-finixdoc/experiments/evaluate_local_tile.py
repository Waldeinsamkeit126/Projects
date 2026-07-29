from __future__ import annotations

import argparse
import json
import os
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from afac2026.table_grid import analyze_table_layout  # noqa: E402
from afac2026.table_tiles import _bounds  # noqa: E402
from afac2026.constrained_table_ocr import (  # noqa: E402
    _rule_grid_boundaries,
    _thin_line_centers,
)


class _Tables(HTMLParser):
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
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def _result_json(result: object) -> dict[str, object]:
    value = getattr(result, "json", result)
    if callable(value):
        value = value()
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise TypeError(type(value))
    nested = value.get("res")
    return nested if isinstance(nested, dict) else value


def _nearest(value: float, centers: list[float]) -> int:
    return min(range(len(centers)), key=lambda index: abs(centers[index] - value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--region", type=int, default=0)
    parser.add_argument("--row-start", type=int, default=12)
    parser.add_argument("--row-end", type=int, default=23)
    parser.add_argument("--column-start", type=int, default=37)
    parser.add_argument("--column-end", type=int, default=73)
    parser.add_argument("--margin-cells", type=int, default=1)
    parser.add_argument("--truth-row-offset", type=int, default=0)
    parser.add_argument("--rule-grid-rows", type=int)
    parser.add_argument("--rule-grid-columns", type=int)
    parser.add_argument("--rule-grid-boundary-columns", type=int)
    parser.add_argument("--header-grid-darkness", type=int, default=180)
    parser.add_argument("--header-grid-coverage", type=float, default=0.65)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--recognition-batch-size", type=int, default=64)
    args = parser.parse_args()

    if (args.rule_grid_rows is None) != (args.rule_grid_columns is None):
        raise ValueError("rule-grid-rows and rule-grid-columns must be used together")
    if args.rule_grid_rows is not None:
        boundary_columns = args.rule_grid_boundary_columns or args.rule_grid_columns
        horizontal, vertical = _rule_grid_boundaries(
            args.image,
            args.rule_grid_rows,
            boundary_columns,
            max_width=6000,
            darkness=220,
            horizontal_coverage=0.50,
        )
        if boundary_columns != args.rule_grid_columns:
            raw_top = max(0, round(horizontal[1]) + 2)
            raw_bottom = max(raw_top + 1, round(horizontal[2]) - 1)
            old_limit = Image.MAX_IMAGE_PIXELS
            Image.MAX_IMAGE_PIXELS = None
            try:
                with Image.open(args.image) as source:
                    header = np.asarray(
                        source.crop((0, raw_top, source.width, raw_bottom)).convert("L")
                    )
            finally:
                Image.MAX_IMAGE_PIXELS = old_limit
            header_mask = header < args.header_grid_darkness
            vertical_active = np.flatnonzero(
                header_mask.sum(axis=0)
                >= max(1, header.shape[0] * args.header_grid_coverage)
            )
            vertical = _thin_line_centers(vertical_active, maximum_thickness=8)
            if len(vertical) != args.rule_grid_columns + 1:
                raise ValueError(
                    "header does not prove requested vertical grid: "
                    f"expected={args.rule_grid_columns + 1}, detected={len(vertical)}"
                )
        row_intervals = list(zip(horizontal, horizontal[1:]))
        column_intervals = list(zip(vertical, vertical[1:]))
        with Image.open(args.image) as source:
            layout_width = source.width
        region_top = round(horizontal[0])
        region_bottom = round(horizontal[-1])
    else:
        layout = analyze_table_layout(args.image)
        region = layout.regions[args.region]
        row_intervals = region.row_intervals
        column_intervals = region.column_intervals
        layout_width = layout.width
        region_top = region.top
        region_bottom = region.bottom
    crop_row_start = max(0, args.row_start - args.margin_cells)
    crop_row_end = min(len(row_intervals), args.row_end + args.margin_cells)
    crop_column_start = max(0, args.column_start - args.margin_cells)
    crop_column_end = min(
        len(column_intervals), args.column_end + args.margin_cells
    )
    x0, x1 = _bounds(
        column_intervals,
        crop_column_start,
        crop_column_end,
        0,
        layout_width,
    )
    y0, y1 = _bounds(
        row_intervals,
        crop_row_start,
        crop_row_end,
        region_top,
        region_bottom,
    )
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(args.image) as source:
            tile = source.crop((x0, y0, x1, y1)).convert("RGB")
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            tile.save(args.destination, quality=95, subsampling=0)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR

    engine = PaddleOCR(
        text_detection_model_name="PP-OCRv6_tiny_det",
        text_detection_model_dir=str(args.model_root / "PP-OCRv6_tiny_det"),
        text_recognition_model_name="PP-OCRv6_tiny_rec",
        text_recognition_model_dir=str(args.model_root / "PP-OCRv6_tiny_rec"),
        text_recognition_batch_size=args.recognition_batch_size,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
        enable_mkldnn=False,
        cpu_threads=8,
    )
    started = time.perf_counter()
    results = list(engine.predict(str(args.destination)))
    elapsed = time.perf_counter() - started
    if len(results) != 1:
        raise RuntimeError(f"unexpected result count: {len(results)}")
    data = _result_json(results[0])
    boxes = data.get("rec_boxes", [])
    texts = data.get("rec_texts", [])
    scores = data.get("rec_scores", [])

    row_centers = [
        (top + bottom) / 2 - y0
        for top, bottom in row_intervals[crop_row_start:crop_row_end]
    ]
    column_centers = [
        (left + right) / 2 - x0
        for left, right in column_intervals[crop_column_start:crop_column_end]
    ]
    assigned: dict[tuple[int, int], list[tuple[float, float, str, float]]] = {}
    for box, text, score in zip(boxes, texts, scores):
        left, top, right, bottom = (float(value) for value in box)
        row = _nearest((top + bottom) / 2, row_centers)
        column = _nearest((left + right) / 2, column_centers)
        assigned.setdefault(
            (crop_row_start + row, crop_column_start + column), []
        ).append((top, left, str(text), float(score)))

    parsed = _Tables()
    parsed.feed(args.ground_truth.read_text(encoding="utf-8"))
    truth = parsed.tables[args.region]
    differences: list[list[object]] = []
    prediction_rows: list[dict[str, object]] = []
    exact = 0
    total = (args.row_end - args.row_start) * (args.column_end - args.column_start)
    for truth_row in range(args.row_start, args.row_end):
        prediction_row: dict[str, object] = {"row": truth_row, "cells": []}
        for truth_column in range(args.column_start, args.column_end):
            pieces = sorted(assigned.get((truth_row, truth_column), []))
            predicted = " ".join(piece[2] for piece in pieces).strip()
            prediction_row["cells"].append([truth_column, predicted])
            expected_row = truth_row + args.truth_row_offset
            if not 0 <= expected_row < len(truth):
                raise ValueError(
                    f"truth row out of range: source={truth_row} offset="
                    f"{args.truth_row_offset} resolved={expected_row}"
                )
            expected = truth[expected_row][truth_column]
            if predicted == expected:
                exact += 1
            elif len(differences) < 40:
                differences.append(
                    [
                        truth_row,
                        truth_column,
                        predicted,
                        expected,
                        round(min((piece[3] for piece in pieces), default=0.0), 4),
                    ]
                )
        prediction_rows.append(prediction_row)

    print(
        json.dumps(
            {
                "crop": [x0, y0, x1, y1],
                "tile_size": [x1 - x0, y1 - y0],
                "elapsed_seconds": round(elapsed, 3),
                "detections": len(texts),
                "cells": total,
                "exact": exact,
                "accuracy": round(exact / total, 6),
                "difference_preview": differences,
                "prediction_rows": prediction_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
