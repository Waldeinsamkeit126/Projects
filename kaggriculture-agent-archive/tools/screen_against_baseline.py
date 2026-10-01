"""Parallel one-baseline screening without the full pairwise matrix."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import statistics
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_matrix as benchmark


def parse_named_path(text: str) -> tuple[str, str]:
    name, separator, path_text = text.partition("=")
    if not separator or not name or not Path(path_text).is_file():
        raise ValueError(f"Expected NAME=PATH, got {text!r}")
    return name, str(Path(path_text).resolve())


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    margins = [float(row["margin_a"]) for row in rows]
    return {
        "games": len(rows),
        "wins": sum(value > 0 for value in margins),
        "ties": sum(value == 0 for value in margins),
        "losses": sum(value < 0 for value in margins),
        "point_rate": sum(1.0 if value > 0 else 0.5 if value == 0 else 0.0 for value in margins) / len(rows),
        "mean_margin": statistics.mean(margins),
        "median_margin": statistics.median(margins),
        "mean_score": statistics.mean(float(row["score_a"]) for row in rows),
        "max_action_seconds": max(float(row["max_action_seconds_a"]) for row in rows),
        "all_done": all(all(status == "DONE" for status in row["statuses"]) for row in rows),
        "by_position": {
            str(position): {
                "games": len(group),
                "point_rate": sum(1.0 if float(row["margin_a"]) > 0 else 0.5 if float(row["margin_a"]) == 0 else 0.0 for row in group) / len(group),
                "mean_margin": statistics.mean(float(row["margin_a"]) for row in group),
            }
            for position in (0, 1)
            if (group := [row for row in rows if int(row["position_a"]) == position])
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--dev-seeds", default="2200-2201")
    parser.add_argument("--holdout-seeds", default="3200-3201")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline_name, baseline_path = parse_named_path(args.baseline)
    variants = dict(parse_named_path(text) for text in args.variant)
    seeds = {
        "dev": benchmark._parse_seeds(args.dev_seeds),
        "holdout": benchmark._parse_seeds(args.holdout_seeds),
    }
    tasks = []
    for name, path in variants.items():
        for split, values in seeds.items():
            for seed in values:
                for position in (0, 1):
                    tasks.append(
                        {
                            "split": split,
                            "seed": seed,
                            "agent_a": name,
                            "agent_b": baseline_name,
                            "path_a": path,
                            "path_b": baseline_path,
                            "position_a": position,
                            "town_center_sell_interval": None,
                        }
                    )
    games = []
    print(f"Running {len(tasks)} games across {len(variants)} variants...", flush=True)
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(benchmark._play_task, task) for task in tasks]
        for index, future in enumerate(as_completed(futures), start=1):
            row = future.result()
            games.append(row)
            print(
                f"[{index:03d}/{len(tasks)}] {row['split']} seed={row['seed']} "
                f"{row['agent_a']}@{row['position_a']} margin={row['margin_a']:+.0f}",
                flush=True,
            )
    summaries = {
        name: {
            "all": summarize([row for row in games if row["agent_a"] == name]),
            "dev": summarize([row for row in games if row["agent_a"] == name and row["split"] == "dev"]),
            "holdout": summarize([row for row in games if row["agent_a"] == name and row["split"] == "holdout"]),
        }
        for name in variants
    }
    payload = {"baseline": baseline_name, "seeds": seeds, "summaries": summaries, "games": games}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
