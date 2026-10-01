"""Local experiment: replay the public #1 agent's action schedule."""

from __future__ import annotations

import json
from pathlib import Path


REPLAY = (
    Path(__file__).resolve().parents[2]
    / "online_episodes"
    / "episode-90752720.json"
)
PLAYER_NAME = "Wufang Hong"


def _load_actions():
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    names = [
        item.get("Name", str(item)) if isinstance(item, dict) else str(item)
        for item in replay["info"]["Agents"]
    ]
    player_index = names.index(PLAYER_NAME)
    return [step[player_index].get("action") for step in replay["steps"]]


ACTIONS = _load_actions()


def agent(obs):
    step = int(obs.get("step", 0) if isinstance(obs, dict) else obs.step)
    action = ACTIONS[step] if 0 <= step < len(ACTIONS) else None
    if not isinstance(action, dict):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(item) for item in (action.get("hands") or [])],
        "market": [list(item) for item in (action.get("market") or [])],
    }
