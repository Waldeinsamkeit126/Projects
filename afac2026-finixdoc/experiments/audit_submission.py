from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.api import _cache_key  # noqa: E402
from afac2026.config import Settings  # noqa: E402
from afac2026.merge import merge_many  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402


def exact_compact_overlap(left: str, right: str, limit: int = 5000) -> int:
    """Longest whitespace-insensitive left suffix / right prefix overlap."""

    a = normalized_for_alignment(left)[-limit:]
    b = normalized_for_alignment(right)[:limit]
    sequence = b + "\0" + a
    prefix = [0] * len(sequence)
    for index in range(1, len(sequence)):
        length = prefix[index - 1]
        while length and sequence[index] != sequence[length]:
            length = prefix[length - 1]
        if sequence[index] == sequence[length]:
            length += 1
        prefix[index] = min(length, len(b))
    return prefix[-1] if prefix else 0


def cached_markdown(image: Path, settings: Settings) -> str:
    key = _cache_key(image, settings.endpoint)
    path = settings.cache_dir / "api" / key / "result.md"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan", type=Path, default=Path("D:/AFAC2026/outputs/a_batch_plan.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/a_submission_audit.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    prediction_dir = settings.output_dir / "predictions_A"
    producers: Counter[str] = Counter()
    strategies: Counter[str] = Counter()
    chars_by_producer: defaultdict[str, list[int]] = defaultdict(list)
    vertical: list[dict[str, object]] = []

    for record in plan["images"]:
        stem = Path(record["file_name"]).stem
        meta = json.loads(
            (prediction_dir / f"{stem}.meta.json").read_text(encoding="utf-8")
        )
        producers[str(meta["producer"])] += 1
        strategies[str(record["strategy"])] += 1
        chars_by_producer[str(meta["producer"])].append(int(meta["chars"]))
        if record["strategy"] != "api_vertical_overlap":
            continue
        crop_dir = settings.cache_dir / "input_crops" / stem
        parts = []
        for crop in record["crops"]:
            name = f"v{crop['index']:03d}_y{crop['top']}_{crop['bottom']}.jpg"
            parts.append(cached_markdown(crop_dir / name, settings))
        merged = merge_many(parts)
        overlaps = [
            exact_compact_overlap(left, right)
            for left, right in zip(parts, parts[1:])
        ]
        vertical.append(
            {
                "file_name": record["file_name"],
                "parts": len(parts),
                "part_chars": sum(map(len, parts)),
                "merged_chars": len(merged),
                "removed_chars": sum(map(len, parts)) - len(merged),
                "exact_compact_overlaps": overlaps,
                "max_exact_compact_overlap": max(overlaps, default=0),
            }
        )

    suspicious = [
        item
        for item in vertical
        if int(item["max_exact_compact_overlap"]) >= 50
        and int(item["removed_chars"])
        < sum(item["exact_compact_overlaps"]) * 0.5
    ]
    report = {
        "producers": dict(producers),
        "strategies": dict(strategies),
        "producer_char_stats": {
            producer: {
                "count": len(values),
                "median": round(statistics.median(values)),
                "sum": sum(values),
            }
            for producer, values in chars_by_producer.items()
        },
        "vertical_images": len(vertical),
        "vertical_pairs": sum(int(item["parts"]) - 1 for item in vertical),
        "vertical_removed_chars": sum(int(item["removed_chars"]) for item in vertical),
        "vertical_exact_overlap_chars": sum(
            sum(item["exact_compact_overlaps"]) for item in vertical
        ),
        "suspicious_vertical_count": len(suspicious),
        "suspicious_vertical": sorted(
            suspicious,
            key=lambda item: int(item["max_exact_compact_overlap"]),
            reverse=True,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(json.dumps({**report, "suspicious_vertical": suspicious[:10]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
