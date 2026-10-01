"""List downloaded episodes that hit a configurable strawberry-field trigger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PLAYER = "KAKA Minishijie"
EPISODE_DIR = Path(__file__).parent / "online_episodes"


def agent_name(value):
    return str(value.get("Name", value)) if isinstance(value, dict) else str(value)


parser = argparse.ArgumentParser()
parser.add_argument("--land", type=int, default=4)
parser.add_argument("--straw", type=int, default=15)
parser.add_argument("--day-min", type=int, default=10)
parser.add_argument("--day-max", type=int, default=17)
args = parser.parse_args()


for path in sorted(EPISODE_DIR.glob("episode-*.json")):
    episode = json.loads(path.read_text(encoding="utf-8"))
    names = [agent_name(agent) for agent in episode["info"]["Agents"]]
    if PLAYER not in names:
        continue
    position = names.index(PLAYER)
    opponent_position = 1 - position
    hit = None
    for step_index, step in enumerate(episode["steps"]):
        observation = step[position].get("observation")
        if not isinstance(observation, dict):
            continue
        day = int(observation.get("day", 0))
        if not args.day_min <= day <= args.day_max:
            continue
        opponent = observation["farms"][opponent_position]
        strawberries = sum(
            1
            for row in opponent["tiles"]
            for tile in row
            if isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
            and tile.get("crop") == "STRAWBERRY"
        )
        lands = len(opponent.get("unlocked_quadrants", ["NW"]))
        if lands >= args.land and strawberries >= args.straw:
            hit = (
                int(observation.get("step", step_index)),
                day,
                int(observation.get("hour", step_index % 24)),
                lands,
                strawberries,
            )
            break
    if hit:
        print(
            f"{path.stem.split('-')[-1]}\t{names[opponent_position]}\tpos={position}"
            f"\tstep={hit[0]}\tday={hit[1]}\thour={hit[2]}\tland={hit[3]}\tstraw={hit[4]}"
        )
