"""Summarize daily asset targets used by high-rated public replays."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def _name(agent: object) -> str:
    if isinstance(agent, dict):
        return str(agent.get("Name", agent))
    return str(agent)


def _state(observation: dict, player: int) -> dict:
    farm = observation["farms"][player]
    crops: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kinds[str(tile.get("kind", "UNKNOWN"))] += 1
            if tile.get("crop"):
                crops[str(tile["crop"])] += 1
            if tile.get("animal"):
                animals[str(tile["animal"])] += 1
    return {
        "money": float(farm.get("money", 0)),
        "hands": len(farm.get("hands", [])),
        "land": len(farm.get("unlocked_quadrants", [])),
        "crops": dict(sorted(crops.items())),
        "animals": dict(sorted(animals.items())),
        "tile_kinds": dict(sorted(kinds.items())),
    }


def summarize(path: Path) -> dict:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = [_name(agent) for agent in replay["info"]["Agents"]]
    players = []
    for player, name in enumerate(names):
        per_day: dict[int, dict] = defaultdict(
            lambda: {
                "market_counts": Counter(),
                "market_quantities": Counter(),
                "first_market": {},
            }
        )
        for step_number, step in enumerate(replay["steps"]):
            record = step[player]
            observation = record["observation"]
            day = int(observation.get("day", step_number // 24))
            hour = int(observation.get("hour", step_number % 24))
            day_row = per_day[day]
            day_row["end"] = _state(observation, player)
            for action in (record.get("action") or {}).get("market", []) or []:
                if not action:
                    continue
                op = str(action[0])
                item = str(action[1]) if len(action) >= 2 else ""
                key = f"{op}:{item}" if item else op
                day_row["market_counts"][key] += 1
                quantity = int(action[2]) if len(action) >= 3 else 1
                day_row["market_quantities"][key] += quantity
                day_row["first_market"].setdefault(
                    key,
                    {"step": step_number, "hour": hour, "action": action},
                )
        players.append(
            {
                "name": name,
                "reward": float(replay["rewards"][player]),
                "days": {
                    str(day): {
                        "end": row["end"],
                        "market_counts": dict(sorted(row["market_counts"].items())),
                        "market_quantities": dict(sorted(row["market_quantities"].items())),
                        "first_market": dict(sorted(row["first_market"].items())),
                    }
                    for day, row in sorted(per_day.items())
                },
            }
        )
    return {
        "episode_id": replay.get("info", {}).get("EpisodeId"),
        "seed": replay.get("info", {}).get("seed"),
        "players": players,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = [summarize(path) for path in args.paths]
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "episodes": len(report)}, indent=2))
    else:
        print(payload)


if __name__ == "__main__":
    main()
