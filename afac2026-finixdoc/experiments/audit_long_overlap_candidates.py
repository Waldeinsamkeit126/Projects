from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.merge import merge_many  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from evaluate_long_overlap_merge import cached_markdown, merge_record  # noqa: E402


def load_csv(path: Path) -> dict[str, str]:
    csv.field_size_limit(1_000_000_000)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["file_name", "ground_truth"]:
            raise ValueError(f"unexpected columns: {reader.fieldnames}")
        return {str(row["file_name"]): str(row["ground_truth"]) for row in reader}


def overridden_sources(output_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for report_name in (
        "afac_A_submission_v2.report.json",
        "afac_A_submission_v3.report.json",
        "afac_A_submission_v5.report.json",
    ):
        report = json.loads((output_dir / report_name).read_text(encoding="utf-8"))
        for item in report.get("overrides", []):
            result[str(item["file_name"])] = str(item["source"])
    report = json.loads(
        (output_dir / "afac_A_submission_v6.report.json").read_text(encoding="utf-8")
    )
    for item in report.get("changes", []):
        result[str(item["file_name"])] = "v6_corner_table"
    return result


def strict_pair_gate(pair: dict[str, object]) -> bool:
    """Stay inside the envelope observed on the five exact-GT controls."""

    return (
        bool(pair["accepted"])
        and float(pair["expected_overlap_fraction"]) >= 0.30
        and int(pair["anchor_lines"]) >= 30
        and float(pair["anchor_coverage"]) >= 0.30
        and 0.98 <= float(pair["fit_slope"]) <= 1.02
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
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v6.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/long_overlap_candidate_audit.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    base = load_csv(args.base)
    overrides = overridden_sources(settings.output_dir)

    rows: list[dict[str, object]] = []
    for record in plan["images"]:
        if record["strategy"] != "api_vertical_overlap":
            continue
        name = str(record["file_name"])
        if name in overrides:
            continue
        stem = Path(name).stem
        crops = [dict(item) for item in record["crops"]]
        crop_dir = settings.cache_dir / "input_crops" / stem
        parts = [
            cached_markdown(
                crop_dir
                / f"v{crop['index']:03d}_y{crop['top']}_{crop['bottom']}.jpg",
                settings,
            )
            for crop in crops
        ]
        baseline = merge_many(parts)
        candidate, pairs, _ = merge_record(parts, crops)
        strict_pairs = [pair for pair in pairs if strict_pair_gate(pair)]
        accepted_pairs = [pair for pair in pairs if bool(pair["accepted"])]
        base_value = base[name]
        baseline_matches_base = (
            normalized_for_alignment(baseline)
            == normalized_for_alignment(base_value)
        )
        rows.append(
            {
                "file_name": name,
                "height": int(record["height"]),
                "crop_count": len(crops),
                "part_characters": list(map(len, parts)),
                "baseline_characters": len(baseline),
                "candidate_characters": len(candidate),
                "removed_characters": len(baseline) - len(candidate),
                "baseline_matches_v6": baseline_matches_base,
                "accepted_pairs": len(accepted_pairs),
                "strict_pairs": len(strict_pairs),
                "strict_candidate": bool(strict_pairs) and baseline_matches_base,
                "pairs": pairs,
            }
        )

    strict = [row for row in rows if bool(row["strict_candidate"])]
    report = {
        "original_vertical_samples": len(rows),
        "samples_with_aligned_pair": sum(int(row["accepted_pairs"]) > 0 for row in rows),
        "strict_candidates": len(strict),
        "strict_removed_characters": sum(int(row["removed_characters"]) for row in strict),
        "strict_file_names": [row["file_name"] for row in strict],
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "rows"},
            ensure_ascii=False,
            indent=2,
        )
    )
    for row in strict:
        print(
            json.dumps(
                {
                    "file_name": row["file_name"],
                    "removed_characters": row["removed_characters"],
                    "accepted_pairs": row["accepted_pairs"],
                    "strict_pairs": row["strict_pairs"],
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
