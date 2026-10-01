"""Compare two replay-evaluation reports on player-one openings."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


PLAYER_NAME = "KAKA Minishijie"


def load_games(paths: list[Path]) -> dict[int, dict]:
    games: dict[int, dict] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for game in payload["games"]:
            games[int(game["episode_id"])] = game
    return games


def agent_name(agent: object) -> str:
    return str(agent.get("Name")) if isinstance(agent, dict) else str(agent)


def opening_signature(path: Path) -> dict:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = [agent_name(agent) for agent in replay["info"]["Agents"]]
    player = names.index(PLAYER_NAME)
    opponent = 1 - player
    observation = None
    for step in replay["steps"]:
        candidate = step[player]["observation"]
        if int(candidate.get("day", 0)) >= 1:
            observation = candidate
            break
    if observation is None:
        observation = replay["steps"][-1][player]["observation"]
    farm = observation["farms"][opponent]
    crops: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kinds[str(tile.get("kind"))] += 1
            if tile.get("crop"):
                crops[str(tile["crop"])] += 1
            if tile.get("animal"):
                animals[str(tile["animal"])] += 1
    return {
        "position": player,
        "opponent": names[opponent],
        "crops": dict(sorted(crops.items())),
        "animals": dict(sorted(animals.items())),
        "kinds": dict(sorted(kinds.items())),
        "money": float(farm.get("money", 0)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", nargs="+", type=Path, required=True)
    parser.add_argument("--candidate", nargs="+", type=Path, required=True)
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    baseline = load_games(args.baseline)
    candidate = load_games(args.candidate)
    rows = []
    grouped: dict[str, list[float]] = defaultdict(list)
    for episode_id in sorted(set(baseline) & set(candidate)):
        opening = opening_signature(args.episode_dir / f"episode-{episode_id}.json")
        if opening["position"] != 1:
            continue
        delta = float(candidate[episode_id]["ours"]) - float(baseline[episode_id]["ours"])
        signature = json.dumps(
            {"crops": opening["crops"], "animals": opening["animals"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        grouped[signature].append(delta)
        rows.append({"episode_id": episode_id, "score_delta": delta, **opening})
    rows.sort(key=lambda row: row["score_delta"], reverse=True)
    summary = {
        "player_one_games": len(rows),
        "candidate_better": sum(row["score_delta"] > 0 for row in rows),
        "baseline_better": sum(row["score_delta"] < 0 for row in rows),
        "ties": sum(row["score_delta"] == 0 for row in rows),
        "mean_delta": sum(row["score_delta"] for row in rows) / max(1, len(rows)),
        "groups": [
            {
                "signature": json.loads(signature),
                "games": len(values),
                "mean_delta": sum(values) / len(values),
                "candidate_better": sum(value > 0 for value in values),
            }
            for signature, values in sorted(
                grouped.items(), key=lambda item: sum(item[1]) / len(item[1]), reverse=True
            )
        ],
    }
    payload = {"summary": summary, "games": rows}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
