"""Inspect the opponent's first complete day-one portfolio in episode replays."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


PLAYER_NAME = "KAKA Minishijie"


def _agent_name(agent: object) -> str:
    if isinstance(agent, dict):
        return str(agent.get("Name", agent))
    return str(agent)


def _portfolio(observation: dict, player_index: int) -> tuple[Counter, Counter]:
    crops: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    farm = observation["farms"][player_index]
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("crop"):
                crops[str(tile["crop"])] += 1
            if tile.get("animal"):
                animals[str(tile["animal"])] += 1
    return crops, animals


def inspect(path: Path) -> dict:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = [_agent_name(agent) for agent in replay["info"]["Agents"]]
    player_index = names.index(PLAYER_NAME)
    opponent_index = 1 - player_index
    step = next(
        step
        for step in replay["steps"]
        if int(step[opponent_index]["observation"].get("day", 0)) >= 1
    )
    record = step[opponent_index]
    observation = record["observation"]
    crops, animals = _portfolio(record["observation"], opponent_index)
    animal_total = sum(animals.values())
    pressure_mixed = animal_total >= 4 and crops.get("CARROT", 0) > 0
    pressure_wheat = animal_total == 0 and crops.get("WHEAT", 0) > 0
    return {
        "episode_id": replay["info"]["EpisodeId"],
        "opponent": names[opponent_index],
        "player_index": player_index,
        "crops": dict(sorted(crops.items())),
        "animals": dict(sorted(animals.items())),
        "animal_total": animal_total,
        "market_prices": dict(sorted(observation.get("market", {}).get("prices", {}).items())),
        "player_money": float(observation["farms"][player_index].get("money", 0.0)),
        "opponent_money": float(observation["farms"][opponent_index].get("money", 0.0)),
        "adaptive_pressure": pressure_mixed or pressure_wheat,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_dir", type=Path)
    parser.add_argument("episode_ids", nargs="+", type=int)
    args = parser.parse_args()
    rows = [
        inspect(args.episode_dir / f"episode-{episode_id}.json")
        for episode_id in args.episode_ids
    ]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
