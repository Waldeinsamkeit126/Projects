from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.constrained_table_ocr import _rule_grid_boundaries  # noqa: E402


def parse_cell(value: str) -> tuple[int, int, str]:
    parts = value.split(",", 2)
    if len(parts) < 2:
        raise argparse.ArgumentTypeError("cell must be ROW,COLUMN[,LABEL]")
    row, column = map(int, parts[:2])
    label = parts[2] if len(parts) == 3 else f"r{row} c{column}"
    return row, column, label


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--cell", type=parse_cell, action="append", required=True)
    parser.add_argument("--scale", type=int, default=8)
    parser.add_argument("--montage-columns", type=int, default=2)
    parser.add_argument("--darkness", type=int, default=200)
    parser.add_argument("--horizontal-coverage", type=float, default=0.65)
    parser.add_argument("--vertical-coverage", type=float, default=0.70)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    horizontal, vertical = _rule_grid_boundaries(
        args.image,
        args.rows,
        args.columns,
        max_width=6000,
        darkness=args.darkness,
        horizontal_coverage=args.horizontal_coverage,
        vertical_coverage=args.vertical_coverage,
    )
    source = Image.open(args.image).convert("RGB")
    cards: list[Image.Image] = []
    for row, column, label in args.cell:
        if not (0 <= row < args.rows and 0 <= column < args.columns):
            raise ValueError(f"cell outside grid: {(row, column)}")
        left = max(0, math.floor(vertical[column]) + 1)
        right = min(source.width, math.ceil(vertical[column + 1]) - 1)
        top = max(0, math.floor(horizontal[row]) + 1)
        bottom = min(source.height, math.ceil(horizontal[row + 1]) - 1)
        crop = source.crop((left, top, right, bottom))
        crop = crop.resize(
            (crop.width * args.scale, crop.height * args.scale),
            Image.Resampling.LANCZOS,
        )
        label_height = 28
        card = Image.new("RGB", (crop.width, crop.height + label_height), "white")
        card.paste(crop, (0, label_height))
        ImageDraw.Draw(card).text((6, 6), label, fill="black")
        cards.append(card)
    width = max(card.width for card in cards)
    height = max(card.height for card in cards)
    montage_columns = min(args.montage_columns, len(cards))
    montage_rows = math.ceil(len(cards) / montage_columns)
    montage = Image.new(
        "RGB",
        (width * montage_columns, height * montage_rows),
        "#d0d0d0",
    )
    for index, card in enumerate(cards):
        x = (index % montage_columns) * width
        y = (index // montage_columns) * height
        montage.paste(card, (x, y))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    montage.save(args.output)
    print(f"{args.output} cells={len(cards)} size={montage.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
