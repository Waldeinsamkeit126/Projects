from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import conservative_normalize, normalized_for_alignment  # noqa: E402
from afac2026.score import levenshtein  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def distance(prediction: str, ground_truth: str) -> float:
    prediction = conservative_normalize(prediction)
    ground_truth = conservative_normalize(ground_truth)
    return levenshtein(prediction, ground_truth) / max(len(ground_truth), 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_conflicting_duplicate_audit.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    gt_by_stem = {path.stem: path for path in data.train_markdowns}
    train_long = [
        path
        for path in data.train_images
        if any("long" in part.lower() for part in path.parts)
    ]
    test_long = [
        path
        for path in data.test_images
        if any("long" in part.lower() for part in path.parts)
    ]
    train_by_hash: defaultdict[str, list[Path]] = defaultdict(list)
    for image in train_long:
        train_by_hash[sha256_file(image)].append(image)

    items = []
    for image in test_long:
        candidates = train_by_hash.get(sha256_file(image), [])
        if len(candidates) < 2:
            continue
        texts = [
            gt_by_stem[candidate.stem].read_text(encoding="utf-8")
            for candidate in candidates
        ]
        if len({normalized_for_alignment(text) for text in texts}) == 1:
            continue
        current = (
            settings.output_dir / "predictions_A" / f"{image.stem}.md"
        ).read_text(encoding="utf-8")
        current_distances = [distance(current, text) for text in texts]
        matrix = [
            [distance(candidate, target) for target in texts]
            for candidate in texts
        ]
        means = [statistics.mean(row) for row in matrix]
        medoid_index = min(range(len(means)), key=lambda index: means[index])
        medoid_distances = matrix[medoid_index]
        wins = sum(
            medoid < baseline
            for medoid, baseline in zip(medoid_distances, current_distances)
        )
        ties = sum(
            abs(medoid - baseline) < 1e-9
            for medoid, baseline in zip(medoid_distances, current_distances)
        )
        item = {
            "file_name": image.name,
            "candidate_count": len(candidates),
            "medoid_train": candidates[medoid_index].name,
            "medoid_gt": str(gt_by_stem[candidates[medoid_index].stem]),
            "current_mean_distance": round(statistics.mean(current_distances), 6),
            "medoid_mean_distance": round(means[medoid_index], 6),
            "mean_gain": round(
                statistics.mean(current_distances) - means[medoid_index], 6
            ),
            "medoid_wins": wins,
            "ties": ties,
            "current_distances": [round(value, 6) for value in current_distances],
            "medoid_distances": [round(value, 6) for value in medoid_distances],
        }
        items.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)

    recommended = [
        item
        for item in items
        if item["mean_gain"] >= 0.03
        and item["medoid_wins"] > item["candidate_count"] / 2
    ]
    report = {
        "conflicting_groups": len(items),
        "recommended_groups": len(recommended),
        "mean_gain_sum_all": round(sum(item["mean_gain"] for item in items), 6),
        "mean_gain_sum_recommended": round(
            sum(item["mean_gain"] for item in recommended), 6
        ),
        "recommended": recommended,
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"items", "recommended"}},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
