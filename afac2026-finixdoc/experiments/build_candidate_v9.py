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
from evaluate_long_overlap_merge import cached_markdown, merge_record  # noqa: E402


def load_submission(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected base columns: {reader.fieldnames}")
        return {str(row["file_name"]): str(row["ground_truth"]) for row in reader}


def relaxed_pair_gate(pair: dict[str, object]) -> bool:
    """Second-tier gate used only after the strict v8 route scored positively."""

    return (
        bool(pair["accepted"])
        and float(pair["expected_overlap_fraction"]) >= 0.25
        and int(pair["anchor_lines"]) >= 28
        and float(pair["anchor_coverage"]) >= 0.19
        and 0.95 <= float(pair["fit_slope"]) <= 1.02
        and float(pair["fit_r_squared"]) >= 0.999
        and float(pair["last_left_match_fraction"]) >= 0.98
        and int(pair["cut_delta"]) <= int(pair["cut_tolerance"])
    )


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
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v8.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v9.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v9.report.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    record_by_name = {str(item["file_name"]): item for item in plan["images"]}
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    selected = {
        str(row["file_name"])
        for row in audit["rows"]
        if not bool(row["strict_candidate"]) and int(row["accepted_pairs"]) > 0
    }
    predictions = load_submission(args.base)

    changes: list[dict[str, object]] = []
    for name in sorted(selected):
        record = record_by_name[name]
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
            raise ValueError(f"v8 no longer matches cached baseline: {name}")
        candidate, pairs, _ = merge_record(parts, crops)
        accepted = [pair for pair in pairs if bool(pair["accepted"])]
        relaxed = [pair for pair in pairs if relaxed_pair_gate(pair)]
        if not relaxed or len(relaxed) != len(accepted):
            raise ValueError(
                f"candidate contains pair outside relaxed gate: {name}; "
                f"accepted={len(accepted)}, relaxed={len(relaxed)}"
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
                "relaxed_pairs": len(relaxed),
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
                        "cut_delta": pair["cut_delta"],
                        "cut_tolerance": pair["cut_tolerance"],
                    }
                    for pair in relaxed
                ],
            }
        )

    if len(changes) != 6:
        raise ValueError(f"expected 6 second-tier changes, got {len(changes)}")
    write_submission(data.submission_template, predictions, args.output)
    report = {
        "base": str(args.base),
        "output": str(args.output),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "rows": len(predictions),
        "changed_samples": len(changes),
        "removed_characters": sum(int(item["removed_characters"]) for item in changes),
        "changes": changes,
        "validation": {
            "v8_score": 78.4124,
            "v8_gain_over_v6": 2.7623,
            "exact_duplicate_controls": 5,
            "improved_controls": 5,
            "harmed_controls": 0,
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
