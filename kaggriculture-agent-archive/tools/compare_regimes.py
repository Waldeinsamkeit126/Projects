"""Compare the V3 and V4 crop regimes across downloaded online replays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspect_openings import inspect


def _rows(report: dict) -> dict[int, dict]:
    source = report.get("games", report.get("episodes", []))
    normalized = {}
    for row in source:
        episode_id = int(row["episode_id"])
        if "ours" in row:
            score = float(row["ours"])
            margin = float(row["margin"])
            win = bool(row["win"])
        else:
            score = float(row["player"]["reward"])
            margin = float(row["margin"])
            win = row["result"] == "win"
        normalized[episode_id] = {"score": score, "margin": margin, "win": win}
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--pair", action="append", nargs=2, metavar=("V3", "V4"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = []
    for v3_path, v4_path in args.pair:
        v3 = _rows(json.loads(Path(v3_path).read_text(encoding="utf-8")))
        v4 = _rows(json.loads(Path(v4_path).read_text(encoding="utf-8")))
        if set(v3) != set(v4):
            raise ValueError(f"Episode mismatch: {v3_path} vs {v4_path}")
        for episode_id in sorted(v3):
            opening = inspect(args.episode_dir / f"episode-{episode_id}.json")
            a, b = v3[episode_id], v4[episode_id]
            preferred = "v4" if (b["win"], b["margin"]) > (a["win"], a["margin"]) else "v3"
            rows.append(
                {
                    **opening,
                    "v3": a,
                    "v4": b,
                    "preferred": preferred,
                    "score_delta_v4_minus_v3": b["score"] - a["score"],
                    "margin_delta_v4_minus_v3": b["margin"] - a["margin"],
                }
            )

    summary = {
        "games": len(rows),
        "v3_wins": sum(row["v3"]["win"] for row in rows),
        "v4_wins": sum(row["v4"]["win"] for row in rows),
        "preferred_v3": sum(row["preferred"] == "v3" for row in rows),
        "preferred_v4": sum(row["preferred"] == "v4" for row in rows),
        "rows": rows,
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, indent=2))
    else:
        print(payload)


if __name__ == "__main__":
    main()
