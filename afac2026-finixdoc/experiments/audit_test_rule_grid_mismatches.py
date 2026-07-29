from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from audit_rule_grid_shapes import expected_shapes  # noqa: E402


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        return {
            str(row["file_name"]): str(row["ground_truth"])
            for row in csv.DictReader(stream)
        }


def cells(shapes: list[tuple[int, int]]) -> int:
    return sum(rows * columns for rows, columns in shapes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--grid-report", type=Path, default=Path("work_rule_grid_test.json")
    )
    parser.add_argument(
        "--submission",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v11.csv"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("work_test_rule_grid_mismatches.json")
    )
    args = parser.parse_args()
    grid = json.loads(args.grid_report.read_text(encoding="utf-8"))
    predictions = load_submission(args.submission)
    items = []
    for source in grid["items"]:
        name = str(source["file_name"])
        detected = [tuple(map(int, shape)) for shape in source["detected"]]
        predicted = expected_shapes(predictions[name])
        if not detected:
            continue
        detected_cells = cells(detected)
        predicted_cells = cells(predicted)
        item = {
            "file_name": name,
            "detected": detected,
            "predicted": predicted,
            "exact": detected == predicted,
            "detected_cells": detected_cells,
            "predicted_cells": predicted_cells,
            "cell_delta": detected_cells - predicted_cells,
            "cell_ratio": round(
                detected_cells / max(1, predicted_cells), 6
            ),
            "width": source["width"],
            "height": source["height"],
        }
        items.append(item)
    mismatches = sorted(
        (item for item in items if not bool(item["exact"])),
        key=lambda item: (
            -abs(int(item["cell_delta"])),
            -float(item["cell_ratio"]),
        ),
    )
    report = {
        "submission": str(args.submission),
        "with_detected_grid": len(items),
        "exact": sum(bool(item["exact"]) for item in items),
        "mismatches": mismatches,
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "with_detected_grid": report["with_detected_grid"],
                "exact": report["exact"],
                "top_mismatches": mismatches[:20],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
