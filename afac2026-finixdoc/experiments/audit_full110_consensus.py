from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.score import _TableParser  # noqa: E402


TARGET = "276f08ab-b337-4baa-87d0-b7ea40c31fbc.jpg"
ROWS = 90
NUMERIC_COLUMNS = 106


def canonical(value: str) -> str:
    value = value.replace("]", "1")
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 3:
        return f"{digits[:-2]}.{digits[-2:]}"
    if digits == "0":
        return "0.00"
    raise ValueError(f"cannot canonicalize {value!r}")


def parse_one(markdown: str) -> list[list[str]]:
    parsed = _TableParser()
    parsed.feed(markdown)
    if parsed.tables != 1:
        raise ValueError(f"expected one table, found {parsed.tables}")
    return parsed.cell_text_rows


def load_prediction(path: Path) -> str:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        matches = [
            str(row["ground_truth"])
            for row in csv.DictReader(stream)
            if str(row["file_name"]) == TARGET
        ]
    if len(matches) != 1:
        raise ValueError(f"expected one target prediction, found {len(matches)}")
    return matches[0]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def interpolate(points: list[tuple[int, float]], x: int) -> float | None:
    lower = sorted((point for point in points if point[0] < x), reverse=True)
    upper = sorted(point for point in points if point[0] > x)
    if lower and upper:
        left, right = lower[0], upper[0]
    elif len(lower) >= 2:
        left, right = lower[1], lower[0]
    elif len(upper) >= 2:
        left, right = upper[0], upper[1]
    else:
        return None
    if left[0] == right[0]:
        return None
    return left[1] + (right[1] - left[1]) * (x - left[0]) / (right[0] - left[0])


def predictions(
    row: int,
    column: int,
    values: list[list[float | None]],
    anchors: list[list[bool]],
    exclude: tuple[int, int] | None = None,
) -> list[float]:
    def usable(r: int, c: int) -> bool:
        return anchors[r][c] and (r, c) != exclude and values[r][c] is not None

    row_points = [
        (other, float(values[row][other]))
        for other in range(NUMERIC_COLUMNS)
        if usable(row, other)
    ]
    age_points = [
        (11 + other // 2, float(values[other][column]))
        for other in range(row % 2, ROWS, 2)
        if usable(other, column)
    ]
    result: list[float] = []
    row_prediction = interpolate(row_points, column)
    if row_prediction is not None:
        result.append(row_prediction)
    age_prediction = interpolate(age_points, 11 + row // 2)
    if age_prediction is not None:
        result.append(age_prediction)
    return result


def loss(candidate: float, estimates: list[float]) -> float:
    residuals = [
        abs(candidate - estimate) / max(abs(estimate), 100.0)
        for estimate in estimates
    ]
    return statistics.median(residuals) if residuals else float("inf")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    local_rows = parse_one(args.local.read_text(encoding="utf-8"))
    cloud_rows = parse_one(load_prediction(args.submission))
    if len(local_rows) != ROWS or len(cloud_rows) != ROWS:
        raise ValueError("target row count changed")

    local: list[list[str | None]] = [[None] * NUMERIC_COLUMNS for _ in range(ROWS)]
    cloud: list[list[str | None]] = [[None] * NUMERIC_COLUMNS for _ in range(ROWS)]
    values: list[list[float | None]] = [[None] * NUMERIC_COLUMNS for _ in range(ROWS)]
    anchors = [[False] * NUMERIC_COLUMNS for _ in range(ROWS)]
    unequal_rows: list[dict[str, int]] = []
    for row_index, (local_row, cloud_row) in enumerate(zip(local_rows, cloud_rows)):
        age = 11 + row_index // 2
        numeric_count = NUMERIC_COLUMNS - age
        local_values = [canonical(value) for value in local_row[4 : 4 + numeric_count]]
        cloud_nonempty = [value for value in cloud_row if value.strip()]
        cloud_values: list[str] | None = None
        if len(cloud_nonempty) == numeric_count + 4:
            cloud_values = [canonical(value) for value in cloud_nonempty[4:]]
        else:
            unequal_rows.append(
                {
                    "row": row_index,
                    "age": age,
                    "expected": numeric_count + 4,
                    "cloud": len(cloud_nonempty),
                }
            )
        for column, value in enumerate(local_values):
            local[row_index][column] = value
            values[row_index][column] = float(value)
        if cloud_values is None:
            continue
        for column, value in enumerate(cloud_values):
            cloud[row_index][column] = value
            anchors[row_index][column] = value == local_values[column]

    cross_validation: list[float] = []
    for row in range(ROWS):
        for column in range(NUMERIC_COLUMNS):
            if not anchors[row][column] or values[row][column] is None:
                continue
            estimates = predictions(row, column, values, anchors, (row, column))
            if estimates:
                predicted = statistics.median(estimates)
                cross_validation.append(
                    abs(float(values[row][column]) - predicted)
                    / max(abs(predicted), 100.0)
                )

    disagreements: list[dict[str, object]] = []
    decisions = {"local": 0, "cloud": 0, "insufficient": 0}
    for row in range(ROWS):
        for column in range(NUMERIC_COLUMNS):
            left, right = local[row][column], cloud[row][column]
            if left is None or right is None or left == right:
                continue
            estimates = predictions(row, column, values, anchors)
            if not estimates:
                decisions["insufficient"] += 1
                source = "local"
                local_loss = cloud_loss = float("inf")
            else:
                local_loss = loss(float(left), estimates)
                cloud_loss = loss(float(right), estimates)
                # The local route was exact on all 3,335 calibration numerics,
                # so only switch when the independent smoothness evidence is
                # decisively stronger for the cloud value.
                source = (
                    "cloud"
                    if cloud_loss < local_loss * 0.25
                    and local_loss - cloud_loss > 0.001
                    else "local"
                )
                decisions[source] += 1
            disagreements.append(
                {
                    "row": row,
                    "age": 11 + row // 2,
                    "gender": "男" if row % 2 == 0 else "女",
                    "numeric_column": column,
                    "local": left,
                    "cloud": right,
                    "estimates": estimates,
                    "local_loss": local_loss,
                    "cloud_loss": cloud_loss,
                    "selected": source,
                }
            )

    report = {
        "local": str(args.local),
        "submission": str(args.submission),
        "local_sha256": hashlib.sha256(args.local.read_bytes()).hexdigest(),
        "submission_sha256": hashlib.sha256(args.submission.read_bytes()).hexdigest(),
        "anchor_cells": sum(sum(row) for row in anchors),
        "unequal_cloud_rows": unequal_rows,
        "cross_validation": {
            "cells": len(cross_validation),
            "median_relative_error": percentile(cross_validation, 0.50),
            "p90_relative_error": percentile(cross_validation, 0.90),
            "p95_relative_error": percentile(cross_validation, 0.95),
            "p99_relative_error": percentile(cross_validation, 0.99),
            "maximum_relative_error": max(cross_validation, default=0.0),
        },
        "disagreement_cells": len(disagreements),
        "decisions": decisions,
        "disagreements": disagreements,
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "disagreements"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
