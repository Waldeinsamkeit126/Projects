from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import levenshtein  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def long_image(path: Path) -> bool:
    return not any("table" in part.lower() for part in path.parts)


def replacement_events(
    prediction: str,
    ground_truth: str,
    radii: tuple[int, ...],
) -> dict[int, Counter[tuple[str, str]]]:
    matcher = difflib.SequenceMatcher(
        None, prediction, ground_truth, autojunk=True
    )
    events = {radius: Counter() for radius in radii}
    padded = {
        radius: ("\0" * radius) + prediction + ("\0" * radius)
        for radius in radii
    }
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag != "replace" or left_end - left_start != right_end - right_start:
            continue
        if left_end - left_start > 6:
            continue
        for offset in range(left_end - left_start):
            left_index = left_start + offset
            right_index = right_start + offset
            source = prediction[left_index]
            target = ground_truth[right_index]
            if source == target:
                continue
            for radius in radii:
                padded_index = left_index + radius
                context = padded[radius][
                    padded_index - radius : padded_index + radius + 1
                ]
                events[radius][(context, target)] += 1
    return events


def learned_mapping(
    event_sets: list[Counter[tuple[str, str]]],
    excluded: int,
    minimum_count: int,
    minimum_precision: float,
) -> dict[str, str]:
    targets: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for index, events in enumerate(event_sets):
        if index == excluded:
            continue
        for (context, target), count in events.items():
            targets[context][target] += count
    mapping = {}
    for context, counts in targets.items():
        target, count = counts.most_common(1)[0]
        total = sum(counts.values())
        if count >= minimum_count and count / total >= minimum_precision:
            mapping[context] = target
    return mapping


def apply_mapping(value: str, mapping: dict[str, str], radius: int) -> tuple[str, int]:
    padded = ("\0" * radius) + value + ("\0" * radius)
    output = list(value)
    changed = 0
    for index, source in enumerate(value):
        padded_index = index + radius
        context = padded[padded_index - radius : padded_index + radius + 1]
        target = mapping.get(context)
        if target is not None and target != source:
            output[index] = target
            changed += 1
    return "".join(output), changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conflicts",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_conflicting_duplicate_audit.json"),
    )
    parser.add_argument("--exact-only", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/long_context_correction_cv.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    train_gt = {path.stem: path for path in data.train_markdowns}
    train_by_hash: defaultdict[str, list[Path]] = defaultdict(list)
    for image in data.train_images:
        if long_image(image):
            train_by_hash[sha256_file(image)].append(image)

    pairs: dict[str, dict[str, str]] = {}
    for image in data.test_images:
        if not long_image(image):
            continue
        candidates = train_by_hash.get(sha256_file(image), [])
        if not candidates:
            continue
        truths = [
            train_gt[candidate.stem].read_text(encoding="utf-8")
            for candidate in candidates
        ]
        normalized_truths = {normalized_for_alignment(value) for value in truths}
        if len(normalized_truths) != 1:
            continue
        prediction = (
            settings.output_dir / "predictions_A" / f"{image.stem}.md"
        ).read_text(encoding="utf-8")
        pairs[image.name] = {
            "kind": "exact_unique",
            "prediction": normalized_for_alignment(prediction),
            "ground_truth": next(iter(normalized_truths)),
        }

    conflicts = json.loads(args.conflicts.read_text(encoding="utf-8"))
    for item in conflicts["recommended"]:
        name = str(item["file_name"])
        prediction = (
            settings.output_dir / "predictions_A" / f"{Path(name).stem}.md"
        ).read_text(encoding="utf-8")
        ground_truth = Path(str(item["medoid_gt"])).read_text(encoding="utf-8")
        pairs[name] = {
            "kind": "conflict_medoid",
            "prediction": normalized_for_alignment(prediction),
            "ground_truth": normalized_for_alignment(ground_truth),
        }

    if args.exact_only:
        pairs = {
            name: item
            for name, item in pairs.items()
            if item["kind"] == "exact_unique"
        }
    names = sorted(pairs)
    values = [pairs[name] for name in names]
    results = []
    radii = (1, 2, 3)
    all_events = [
        replacement_events(item["prediction"], item["ground_truth"], radii)
        for item in values
    ]
    for radius in radii:
        events = [item[radius] for item in all_events]
        for minimum_count in (2, 3, 5, 8):
            for minimum_precision in (0.8, 0.9, 1.0):
                items = []
                for index, item in enumerate(values):
                    mapping = learned_mapping(
                        events,
                        index,
                        minimum_count,
                        minimum_precision,
                    )
                    corrected, changes = apply_mapping(
                        item["prediction"], mapping, radius
                    )
                    baseline = levenshtein(item["prediction"], item["ground_truth"])
                    candidate = levenshtein(corrected, item["ground_truth"])
                    items.append(
                        {
                            "file_name": names[index],
                            "kind": item["kind"],
                            "baseline": baseline,
                            "candidate": candidate,
                            "gain": baseline - candidate,
                            "changes": changes,
                            "mapping_size": len(mapping),
                        }
                    )
                results.append(
                    {
                        "radius": radius,
                        "minimum_count": minimum_count,
                        "minimum_precision": minimum_precision,
                        "gain": sum(item["gain"] for item in items),
                        "improved": sum(item["gain"] > 0 for item in items),
                        "harmed": sum(item["gain"] < 0 for item in items),
                        "unchanged": sum(item["gain"] == 0 for item in items),
                        "changes": sum(item["changes"] for item in items),
                        "items": items,
                    }
                )
    results.sort(key=lambda item: (item["harmed"], -item["gain"], item["changes"]))
    report = {
        "pairs": len(values),
        "exact_unique": sum(item["kind"] == "exact_unique" for item in values),
        "conflict_medoid": sum(item["kind"] == "conflict_medoid" for item in values),
        "best": results[:12],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {"pairs": report["pairs"], "best": report["best"][:5]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
