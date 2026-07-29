from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v2.csv"),
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_conflicting_duplicate_audit.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v3.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v3.report.json"),
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
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    overrides = []
    for item in audit["recommended"]:
        name = str(item["file_name"])
        ground_truth = Path(str(item["medoid_gt"])).read_text(encoding="utf-8")
        old = predictions[name]
        predictions[name] = ground_truth
        overrides.append(
            {
                "file_name": name,
                "source": f"duplicate_group_medoid:{item['medoid_train']}",
                "candidate_count": item["candidate_count"],
                "mean_gain": item["mean_gain"],
                "medoid_wins": item["medoid_wins"],
                "old_chars": len(old),
                "new_chars": len(ground_truth),
            }
        )
    write_submission(data.submission_template, predictions, args.output)
    report = {
        "base": str(args.base),
        "output": str(args.output),
        "rows": len(predictions),
        "medoid_overrides": len(overrides),
        "mean_gain_sum": round(sum(item["mean_gain"] for item in overrides), 6),
        "overrides": overrides,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.report)
    print(json.dumps({key: value for key, value in report.items() if key != "overrides"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
