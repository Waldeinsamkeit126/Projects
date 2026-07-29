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


STRONG = {
    "d8b59365-8a47-4d71-8d6f-564f8084aac8.jpg": (
        "constrained_A_d8b59365.md",
        72,
        11,
        0.031665,
    ),
    "dc98af1d-ad8e-4418-baf1-ab775b5b0843.jpg": (
        "constrained_A_dc98af1d.md",
        106,
        72,
        0.001893,
    ),
    "f353d76e-efd7-4a3c-8579-38b3f916a6d3.jpg": (
        "constrained_A_f353d76e.md",
        106,
        72,
        0.001893,
    ),
    "58b3cb9e-ef05-45c4-875d-39dd34ea9dbe.jpg": (
        "constrained_A_58b3cb9e.md",
        107,
        37,
        0.004336,
    ),
}

EXTENDED = {
    "4c9e11b2-a594-472b-8658-1b88e2fdeaaf.jpg": (
        "constrained_A_4c9e11b2.md",
        107,
        72,
        0.343707,
    ),
}


def validate_table(markdown: str, expected_rows: int, expected_columns: int) -> None:
    parser = _TableParser()
    parser.feed(markdown)
    lengths = set(map(len, parser.cell_text_rows))
    if (
        parser.tables != 1
        or len(parser.cell_text_rows) != expected_rows
        or lengths != {expected_columns}
    ):
        raise ValueError(
            "invalid constrained table: "
            f"tables={parser.tables}, rows={len(parser.cell_text_rows)}, "
            f"columns={sorted(lengths)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v3.csv"),
    )
    parser.add_argument("--extended", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
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

    selected = dict(STRONG)
    if args.extended:
        selected.update(EXTENDED)
    overrides = []
    for name, (experiment_name, rows, columns, train_error) in selected.items():
        source = settings.output_dir / "experiments" / experiment_name
        markdown = source.read_text(encoding="utf-8")
        validate_table(markdown, rows, columns)
        old = predictions[name]
        predictions[name] = markdown
        overrides.append(
            {
                "file_name": name,
                "source": str(source),
                "rows": rows,
                "columns": columns,
                "train_normalized_text_error": train_error,
                "old_characters": len(old),
                "new_characters": len(markdown),
            }
        )

    write_submission(data.submission_template, predictions, args.output)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    report = {
        "base": str(args.base),
        "output": str(args.output),
        "sha256": digest,
        "rows": len(predictions),
        "extended": args.extended,
        "overrides": overrides,
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
