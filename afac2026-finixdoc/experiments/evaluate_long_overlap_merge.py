from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.api import _cache_key  # noqa: E402
from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.merge import merge_many  # noqa: E402
from afac2026.normalize import conservative_normalize  # noqa: E402
from afac2026.score import diagnose  # noqa: E402


def cached_markdown(image: Path, settings: Settings) -> str:
    key = _cache_key(image, settings.endpoint)
    path = settings.cache_dir / "api" / key / "result.md"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def normalized_line(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _linear_fit(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    total_weight = sum(weight for _, _, weight in points)
    mean_x = sum(x * weight for x, _, weight in points) / total_weight
    mean_y = sum(y * weight for _, y, weight in points) / total_weight
    variance = sum(weight * (x - mean_x) ** 2 for x, _, weight in points)
    if variance <= 0:
        return 1.0, mean_y - mean_x, 0.0
    covariance = sum(weight * (x - mean_x) * (y - mean_y) for x, y, weight in points)
    slope = covariance / variance
    intercept = mean_y - slope * mean_x
    residual = sum(
        weight * (y - (slope * x + intercept)) ** 2 for x, y, weight in points
    )
    baseline = sum(weight * (y - mean_y) ** 2 for _, y, weight in points)
    r_squared = 1.0 - residual / baseline if baseline else 1.0
    return slope, intercept, r_squared


def merge_adjacent_aligned(
    left: str,
    right: str,
    expected_overlap_fraction: float,
) -> tuple[str, dict[str, object]]:
    """Remove a large repeated crop prefix using exact line anchors.

    The official model is deterministic enough that repeated crop regions
    usually contain many identical non-empty lines.  We fit the monotonic line
    mapping and extrapolate only from the final third of the left crop.  A
    pixel-derived cut is retained as a diagnostic, never as the sole signal.
    """

    left_lines = conservative_normalize(left).splitlines()
    right_lines = conservative_normalize(right).splitlines()
    left_items = [
        (index, normalized_line(line))
        for index, line in enumerate(left_lines)
        if normalized_line(line)
    ]
    right_items = [
        (index, normalized_line(line))
        for index, line in enumerate(right_lines)
        if normalized_line(line)
    ]
    left_values = [value for _, value in left_items]
    right_values = [value for _, value in right_items]
    matcher = SequenceMatcher(None, left_values, right_values, autojunk=False)

    points: list[tuple[float, float, float]] = []
    matching_characters = 0
    last_left_match = -1
    last_right_match = -1
    block_count = 0
    for block in matcher.get_matching_blocks():
        if not block.size:
            continue
        block_count += 1
        for offset in range(block.size):
            left_index = block.a + offset
            right_index = block.b + offset
            weight = max(1, len(left_values[left_index]))
            points.append((float(left_index), float(right_index), float(weight)))
            matching_characters += weight
            last_left_match = max(last_left_match, left_index)
            last_right_match = max(last_right_match, right_index)

    expected_nonempty_cut = round(expected_overlap_fraction * len(right_items))
    if len(points) < 2:
        metadata = {
            "accepted": False,
            "reason": "too_few_exact_line_anchors",
            "anchor_lines": len(points),
            "expected_cut_nonempty": expected_nonempty_cut,
        }
        return "\n".join(left_lines + right_lines).strip(), metadata

    # Anchors late in the left crop best predict where its bottom lands in the
    # right crop.  Fall back to every anchor only when the late region is thin.
    late_threshold = len(left_items) * 0.55
    late_points = [point for point in points if point[0] >= late_threshold]
    fit_points = late_points if len(late_points) >= 3 else points
    slope, intercept, r_squared = _linear_fit(fit_points)
    predicted_cut = round(slope * len(left_items) + intercept)
    predicted_cut = max(0, min(predicted_cut, len(right_items)))
    cut_delta = abs(predicted_cut - expected_nonempty_cut)
    cut_tolerance = max(5, round(len(right_items) * 0.12))
    anchor_coverage = matching_characters / max(
        1, min(sum(map(len, left_values)), sum(map(len, right_values)))
    )
    last_left_fraction = (last_left_match + 1) / max(1, len(left_items))
    accepted = (
        len(fit_points) >= 3
        and 0.75 <= slope <= 1.25
        and r_squared >= 0.97
        and anchor_coverage >= 0.08
        and last_left_fraction >= 0.75
        and cut_delta <= cut_tolerance
    )
    if predicted_cut >= len(right_items):
        raw_cut = len(right_lines)
    else:
        raw_cut = right_items[predicted_cut][0]
    merged = "\n".join(left_lines + right_lines[raw_cut:]).strip()
    metadata = {
        "accepted": accepted,
        "reason": "accepted" if accepted else "quality_gate",
        "left_lines": len(left_lines),
        "right_lines": len(right_lines),
        "left_nonempty_lines": len(left_items),
        "right_nonempty_lines": len(right_items),
        "anchor_lines": len(points),
        "late_anchor_lines": len(late_points),
        "matching_blocks": block_count,
        "matching_characters": matching_characters,
        "anchor_coverage": round(anchor_coverage, 6),
        "fit_slope": round(slope, 6),
        "fit_intercept": round(intercept, 3),
        "fit_r_squared": round(r_squared, 6),
        "last_left_match_fraction": round(last_left_fraction, 6),
        "expected_cut_nonempty": expected_nonempty_cut,
        "predicted_cut_nonempty": predicted_cut,
        "cut_delta": cut_delta,
        "cut_tolerance": cut_tolerance,
        "raw_cut_line": raw_cut,
    }
    return merged, metadata


def merge_record(
    parts: list[str], crops: list[dict[str, int]]
) -> tuple[str, list[dict[str, object]], bool]:
    result = parts[0]
    reports: list[dict[str, object]] = []
    all_accepted = True
    for index, part in enumerate(parts[1:], start=1):
        previous = crops[index - 1]
        current = crops[index]
        overlap = max(0, int(previous["bottom"]) - int(current["top"]))
        current_height = int(current["bottom"]) - int(current["top"])
        fraction = overlap / max(1, current_height)
        candidate, report = merge_adjacent_aligned(result, part, fraction)
        report = {
            "pair_index": index - 1,
            "pixel_overlap": overlap,
            "expected_overlap_fraction": round(fraction, 6),
            **report,
        }
        reports.append(report)
        if bool(report["accepted"]):
            result = candidate
        else:
            # Preserve the established conservative behavior for weak pairs.
            result = merge_many([result, part])
            all_accepted = False
    return conservative_normalize(result), reports, all_accepted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan", type=Path, default=Path("D:/AFAC2026/outputs/a_batch_plan.json")
    )
    parser.add_argument(
        "--exact-report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v2.report.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/long_overlap_merge_cv.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    by_name = {str(item["file_name"]): item for item in plan["images"]}
    gt_by_stem = {path.stem: path for path in data.train_markdowns}
    exact_report = json.loads(args.exact_report.read_text(encoding="utf-8"))

    rows: list[dict[str, object]] = []
    for override in exact_report["overrides"]:
        source = str(override["source"])
        if not source.startswith("exact_train_duplicate:"):
            continue
        name = str(override["file_name"])
        record = by_name[name]
        if record["strategy"] != "api_vertical_overlap":
            continue
        stem = Path(source.split(":", 1)[1]).stem
        ground_truth = gt_by_stem[stem].read_text(encoding="utf-8")
        crop_dir = settings.cache_dir / "input_crops" / Path(name).stem
        crops = [dict(item) for item in record["crops"]]
        parts = [
            cached_markdown(
                crop_dir
                / f"v{crop['index']:03d}_y{crop['top']}_{crop['bottom']}.jpg",
                settings,
            )
            for crop in crops
        ]
        baseline = merge_many(parts)
        candidate, pair_reports, all_accepted = merge_record(parts, crops)
        baseline_score = diagnose(baseline, ground_truth)
        candidate_score = diagnose(candidate, ground_truth)
        rows.append(
            {
                "file_name": name,
                "train_source": Path(source.split(":", 1)[1]).name,
                "parts": len(parts),
                "part_characters": list(map(len, parts)),
                "baseline_characters": len(baseline),
                "candidate_characters": len(candidate),
                "ground_truth_characters": len(ground_truth),
                "all_pairs_accepted": all_accepted,
                "baseline_error": baseline_score.text_normalized_distance,
                "candidate_error": candidate_score.text_normalized_distance,
                "error_gain": round(
                    baseline_score.text_normalized_distance
                    - candidate_score.text_normalized_distance,
                    9,
                ),
                "pairs": pair_reports,
            }
        )

    report = {
        "samples": len(rows),
        "all_pairs_accepted_samples": sum(bool(row["all_pairs_accepted"]) for row in rows),
        "improved_samples": sum(float(row["error_gain"]) > 0 for row in rows),
        "harmed_samples": sum(float(row["error_gain"]) < 0 for row in rows),
        "baseline_mean_error": statistics.mean(
            float(row["baseline_error"]) for row in rows
        ),
        "candidate_mean_error": statistics.mean(
            float(row["candidate_error"]) for row in rows
        ),
        "total_error_gain": sum(float(row["error_gain"]) for row in rows),
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
    for row in rows:
        print(
            json.dumps(
                {
                    "file_name": row["file_name"],
                    "accepted": row["all_pairs_accepted"],
                    "baseline_error": round(float(row["baseline_error"]), 6),
                    "candidate_error": round(float(row["candidate_error"]), 6),
                    "gain": row["error_gain"],
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
