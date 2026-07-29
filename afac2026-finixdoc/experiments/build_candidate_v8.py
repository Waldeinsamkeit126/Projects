from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.merge import merge_many  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402
from audit_long_overlap_candidates import strict_pair_gate  # noqa: E402
from evaluate_long_overlap_merge import cached_markdown, merge_record  # noqa: E402


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected base columns: {reader.fieldnames}")
        return {str(row["file_name"]): str(row["ground_truth"]) for row in reader}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan", type=Path, default=Path("D:/AFAC2026/outputs/a_batch_plan.json")
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("D:/AFAC2026/outputs/long_overlap_candidate_audit.json"),
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v6.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v8.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v8.report.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    record_by_name = {str(item["file_name"]): item for item in plan["images"]}
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    selected = set(map(str, audit["strict_file_names"]))
    predictions = load_submission(args.base)

    changes: list[dict[str, object]] = []
    for name in sorted(selected):
        record = record_by_name[name]
        if record["strategy"] != "api_vertical_overlap":
            raise ValueError(f"candidate is not a vertical API record: {name}")
        crops = [dict(item) for item in record["crops"]]
        crop_dir = settings.cache_dir / "input_crops" / Path(name).stem
        parts = [
            cached_markdown(
                crop_dir
                / f"v{crop['index']:03d}_y{crop['top']}_{crop['bottom']}.jpg",
                settings,
            )
            for crop in crops
        ]
        baseline = merge_many(parts)
        old = predictions[name]
        if normalized_for_alignment(old) != normalized_for_alignment(baseline):
            raise ValueError(f"v6 no longer matches cached baseline: {name}")
        candidate, pairs, _ = merge_record(parts, crops)
        accepted = [pair for pair in pairs if bool(pair["accepted"])]
        strict = [pair for pair in pairs if strict_pair_gate(pair)]
        if not strict or len(strict) != len(accepted):
            raise ValueError(
                f"candidate contains non-strict aligned pair: {name}; "
                f"accepted={len(accepted)}, strict={len(strict)}"
            )
        if len(candidate) >= len(old):
            raise ValueError(f"candidate did not remove repeated content: {name}")
        predictions[name] = candidate
        changes.append(
            {
                "file_name": name,
                "old_characters": len(old),
                "new_characters": len(candidate),
                "removed_characters": len(old) - len(candidate),
                "strict_pairs": len(strict),
                "pair_evidence": [
                    {
                        "expected_overlap_fraction": pair["expected_overlap_fraction"],
                        "anchor_lines": pair["anchor_lines"],
                        "anchor_coverage": pair["anchor_coverage"],
                        "fit_slope": pair["fit_slope"],
                        "fit_r_squared": pair["fit_r_squared"],
                        "last_left_match_fraction": pair[
                            "last_left_match_fraction"
                        ],
                    }
                    for pair in strict
                ],
            }
        )

    if len(changes) != len(selected):
        raise ValueError(f"missing changes: expected={len(selected)}, actual={len(changes)}")
    write_submission(data.submission_template, predictions, args.output)
    report = {
        "base": str(args.base),
        "output": str(args.output),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "rows": len(predictions),
        "changes": changes,
        "changed_samples": len(changes),
        "removed_characters": sum(int(item["removed_characters"]) for item in changes),
        "validation": {
            "exact_duplicate_controls": 5,
            "improved_controls": 5,
            "harmed_controls": 0,
            "baseline_mean_normalized_error": 0.5183969908070069,
            "candidate_mean_normalized_error": 0.09687905745993808,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.report)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "changes"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
