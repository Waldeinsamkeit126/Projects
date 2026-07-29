from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.constrained_table_ocr import _rule_grid_boundaries  # noqa: E402
from audit_two_triangular_integer_tables import parse_tables  # noqa: E402


def digit_components(
    cell: np.ndarray,
    *,
    threshold: int,
    minimum_height_ratio: float,
) -> list[np.ndarray]:
    mask = (cell < threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components: list[tuple[int, int, int, int, int, np.ndarray]] = []
    for label in range(1, count):
        left, top, width, height, area = (int(value) for value in stats[label])
        if area < 2 or width <= 0 or height <= 0:
            continue
        piece = np.full((height, width), 255, dtype=np.uint8)
        component_mask = labels[top : top + height, left : left + width] == label
        source = cell[top : top + height, left : left + width]
        piece[component_mask] = source[component_mask]
        components.append((left, top, width, height, area, piece))
    if not components:
        return []
    maximum_height = max(item[3] for item in components)
    minimum_height = max(4, round(maximum_height * minimum_height_ratio))
    digits = [item for item in components if item[3] >= minimum_height and item[4] >= 4]
    return [item[-1] for item in sorted(digits, key=lambda item: item[0])]


def normalized(piece: np.ndarray, size: tuple[int, int] = (20, 28)) -> np.ndarray:
    target_width, target_height = size
    height, width = piece.shape
    scale = min((target_height - 2) / max(height, 1), (target_width - 2) / max(width, 1))
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = Image.fromarray(piece).resize(
        (resized_width, resized_height), Image.Resampling.BILINEAR
    )
    canvas = np.full((target_height, target_width), 255, dtype=np.uint8)
    left = (target_width - resized_width) // 2
    top = (target_height - resized_height) // 2
    canvas[top : top + resized_height, left : left + resized_width] = np.asarray(resized)
    return (255 - canvas.astype(np.float32)) / 255.0


def cell_image(
    gray: np.ndarray,
    horizontal: list[float],
    vertical: list[float],
    row: int,
    column: int,
    inset: int,
) -> np.ndarray:
    left = max(0, int(np.ceil(vertical[column])) + inset)
    right = min(gray.shape[1], int(np.floor(vertical[column + 1])) - inset)
    top = max(0, int(np.ceil(horizontal[row])) + inset)
    bottom = min(gray.shape[0], int(np.floor(horizontal[row + 1])) - inset)
    if right <= left or bottom <= top:
        return np.empty((0, 0), dtype=np.uint8)
    return gray[top:bottom, left:right]


def build_samples(
    gray: np.ndarray,
    horizontal: list[float],
    vertical: list[float],
    truth: list[list[str]],
    selected_rows: set[int],
    *,
    inset: int,
    threshold: int,
    minimum_height_ratio: float,
) -> tuple[dict[str, list[np.ndarray]], int]:
    samples: dict[str, list[np.ndarray]] = defaultdict(list)
    aligned_cells = 0
    for row in sorted(selected_rows):
        for column in range(len(vertical) - 1):
            expected = truth[row][column + 1].strip()
            if not expected or expected == "-":
                continue
            expected_digits = re.sub(r"\D", "", expected)
            pieces = digit_components(
                cell_image(gray, horizontal, vertical, row, column, inset),
                threshold=threshold,
                minimum_height_ratio=minimum_height_ratio,
            )
            if len(pieces) != len(expected_digits):
                continue
            aligned_cells += 1
            for character, piece in zip(expected_digits, pieces):
                samples[character].append(normalized(piece))
    return samples, aligned_cells


def templates_from(samples: dict[str, list[np.ndarray]]) -> dict[str, np.ndarray]:
    return {
        character: np.median(np.stack(values), axis=0)
        for character, values in samples.items()
        if len(values) >= 5
    }


def classify(piece: np.ndarray, templates: dict[str, np.ndarray]) -> str:
    value = normalized(piece)
    return min(
        templates,
        key=lambda character: float(np.mean((value - templates[character]) ** 2)),
    )


def evaluate(
    gray: np.ndarray,
    horizontal: list[float],
    vertical: list[float],
    truth: list[list[str]],
    selected_rows: set[int],
    templates: dict[str, np.ndarray],
    *,
    inset: int,
    threshold: int,
    minimum_height_ratio: float,
) -> dict[str, object]:
    total_cells = segmentable_cells = exact_cells = 0
    total_characters = exact_characters = 0
    differences: list[dict[str, object]] = []
    segmentation_failures: list[dict[str, object]] = []
    for row in sorted(selected_rows):
        for column in range(len(vertical) - 1):
            expected = truth[row][column + 1].strip()
            if not expected or expected == "-":
                continue
            expected_digits = re.sub(r"\D", "", expected)
            total_cells += 1
            pieces = digit_components(
                cell_image(gray, horizontal, vertical, row, column, inset),
                threshold=threshold,
                minimum_height_ratio=minimum_height_ratio,
            )
            if len(pieces) != len(expected_digits):
                if len(segmentation_failures) < 30:
                    segmentation_failures.append(
                        {
                            "row": row,
                            "column": column,
                            "expected": expected_digits,
                            "components": len(pieces),
                        }
                    )
                continue
            segmentable_cells += 1
            predicted = "".join(classify(piece, templates) for piece in pieces)
            total_characters += len(expected_digits)
            exact_characters += sum(a == b for a, b in zip(predicted, expected_digits))
            if predicted == expected_digits:
                exact_cells += 1
            elif len(differences) < 40:
                differences.append(
                    {
                        "row": row,
                        "column": column,
                        "predicted": predicted,
                        "expected": expected_digits,
                    }
                )
    return {
        "total_cells": total_cells,
        "segmentable_cells": segmentable_cells,
        "segmentation_rate": segmentable_cells / max(1, total_cells),
        "exact_cells": exact_cells,
        "exact_cell_rate_all": exact_cells / max(1, total_cells),
        "exact_cell_rate_segmentable": exact_cells / max(1, segmentable_cells),
        "total_characters": total_characters,
        "exact_characters": exact_characters,
        "exact_character_rate": exact_characters / max(1, total_characters),
        "segmentation_failures": segmentation_failures,
        "differences": differences,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--inset", type=int, default=1)
    parser.add_argument("--threshold", type=int, default=210)
    parser.add_argument("--minimum-height-ratio", type=float, default=0.55)
    parser.add_argument("--max-width", type=int, default=6000)
    parser.add_argument("--darkness", type=int, default=200)
    parser.add_argument("--horizontal-coverage", type=float, default=0.65)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tables = parse_tables(args.ground_truth.read_text(encoding="utf-8"))
    if len(tables) != 1:
        raise ValueError(f"expected one ground-truth table, found {len(tables)}")
    truth = tables[0].cell_text_rows
    if len(truth) != args.rows or any(len(row) != args.columns + 1 for row in truth):
        raise ValueError("ground truth is not one external-key column wider than the grid")
    horizontal, vertical = _rule_grid_boundaries(
        args.image,
        args.rows,
        args.columns,
        max_width=args.max_width,
        darkness=args.darkness,
        horizontal_coverage=args.horizontal_coverage,
    )
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(args.image) as source:
            gray = np.asarray(source.convert("L"))
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit

    folds: list[dict[str, object]] = []
    for test_parity in (0, 1):
        test_rows = {row for row in range(args.rows) if row % 2 == test_parity}
        train_rows = set(range(args.rows)) - test_rows
        samples, aligned = build_samples(
            gray,
            horizontal,
            vertical,
            truth,
            train_rows,
            inset=args.inset,
            threshold=args.threshold,
            minimum_height_ratio=args.minimum_height_ratio,
        )
        templates = templates_from(samples)
        evaluation = evaluate(
            gray,
            horizontal,
            vertical,
            truth,
            test_rows,
            templates,
            inset=args.inset,
            threshold=args.threshold,
            minimum_height_ratio=args.minimum_height_ratio,
        )
        folds.append(
            {
                "test_parity": test_parity,
                "training_aligned_cells": aligned,
                "sample_counts": {key: len(value) for key, value in sorted(samples.items())},
                "templates": sorted(templates),
                "evaluation": evaluation,
            }
        )

    totals = {
        key: sum(int(fold["evaluation"][key]) for fold in folds)  # type: ignore[index]
        for key in (
            "total_cells",
            "segmentable_cells",
            "exact_cells",
            "total_characters",
            "exact_characters",
        )
    }
    result = {
        "image": str(args.image),
        "ground_truth": str(args.ground_truth),
        "parameters": {
            "rows": args.rows,
            "columns": args.columns,
            "inset": args.inset,
            "threshold": args.threshold,
            "minimum_height_ratio": args.minimum_height_ratio,
        },
        "totals": {
            **totals,
            "segmentation_rate": totals["segmentable_cells"] / max(1, totals["total_cells"]),
            "exact_cell_rate_all": totals["exact_cells"] / max(1, totals["total_cells"]),
            "exact_cell_rate_segmentable": totals["exact_cells"]
            / max(1, totals["segmentable_cells"]),
            "exact_character_rate": totals["exact_characters"]
            / max(1, totals["total_characters"]),
        },
        "folds": folds,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(json.dumps(result["totals"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
