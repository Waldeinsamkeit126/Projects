"""Inspect the step-zero public farm state in Kaggriculture replays."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


PLAYER_NAME = "KAKA Minishijie"


def _agent_name(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(agent.get("Name", agent))
    return str(agent)


def _farm_summary(farm: dict[str, Any]) -> dict[str, Any]:
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
        "money": float(farm.get("money", 0.0)),
        "hands": len(farm.get("hands", [])),
        "unlocked_quadrants": len(farm.get("unlocked_quadrants", [])),
        "crops": dict(sorted(crops.items())),
        "animals": dict(sorted(animals.items())),
        "tile_kinds": dict(sorted(kinds.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_dir", type=Path)
    parser.add_argument("ids", nargs="+", type=int)
    args = parser.parse_args()

    rows = []
    for episode_id in args.ids:
        path = args.episode_dir / f"episode-{episode_id}.json"
        replay = json.loads(path.read_text(encoding="utf-8"))
        names = [_agent_name(agent) for agent in replay["info"]["Agents"]]
        player_index = names.index(PLAYER_NAME)
        opponent_index = 1 - player_index
        observation = replay["steps"][0][player_index]["observation"]
        rows.append(
            {
                "episode_id": episode_id,
                "seed": replay.get("info", {}).get("seed"),
                "player_index": player_index,
                "opponent": names[opponent_index],
                "opponent_initial": _farm_summary(
                    observation["farms"][opponent_index]
                ),
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
