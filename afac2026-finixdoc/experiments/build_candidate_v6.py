from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.score import _TableParser  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


OVERRIDES = {
    "f3cfab65-77d7-4c72-8f40-b4bc14624f52.jpg": "corner_A_f3cfab65.md",
    "8e60d5f8-1462-4d57-bcfa-3cc5c3a82d2a.jpg": "corner_A_8e60d5f8.md",
}


def validate_corner_table(markdown: str, rows: int = 107, columns: int = 72) -> None:
    parsed = _TableParser()
    parsed.feed(markdown)
    lengths = [len(row) for row in parsed.rows]
    expected_lengths = [2, columns - 1, *([columns] * (rows - 2))]
    expected_first = (
        ("td", "2", None),
        ("td", None, str(columns - 1)),
    )
    if (
        parsed.tables != 1
        or lengths != expected_lengths
        or tuple(parsed.rows[0]) != expected_first
    ):
        raise ValueError(
            "invalid corner-header table: "
            f"tables={parsed.tables}, rows={len(lengths)}, "
            f"first_lengths={lengths[:3]}, first_signature={parsed.rows[:1]}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v5.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v6.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v6.report.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    csv.field_size_limit(1_000_000_000)
    with args.base.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected base columns: {reader.fieldnames}")
        predictions = {
            str(row["file_name"]): str(row["ground_truth"]) for row in reader
        }

    changes = []
    for name, experiment_name in OVERRIDES.items():
        source = settings.output_dir / "experiments" / experiment_name
        markdown = source.read_text(encoding="utf-8")
        validate_corner_table(markdown)
        old = predictions[name]
        predictions[name] = markdown
        changes.append(
            {
                "file_name": name,
                "source": str(source),
                "training_normalized_text_error": 0.001276,
                "old_characters": len(old),
                "new_characters": len(markdown),
            }
        )

    write_submission(data.submission_template, predictions, args.output)
    report = {
        "base": str(args.base),
        "output": str(args.output),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "rows": len(predictions),
        "changes": changes,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
