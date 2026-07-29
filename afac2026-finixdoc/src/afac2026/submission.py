from __future__ import annotations

import csv
from pathlib import Path

from .normalize import conservative_normalize


def write_submission(template: Path, predictions: dict[str, str], destination: Path) -> None:
    with template.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    expected = {row["file_name"] for row in rows}
    actual = set(predictions)
    if expected != actual:
        raise ValueError(
            f"预测文件名不完整: 缺少={sorted(expected-actual)}, 多余={sorted(actual-expected)}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file_name", "ground_truth"])
        writer.writeheader()
        for row in rows:
            name = row["file_name"]
            writer.writerow({"file_name": name, "ground_truth": conservative_normalize(predictions[name])})
    temp.replace(destination)
