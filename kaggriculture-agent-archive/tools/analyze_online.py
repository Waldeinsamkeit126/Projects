"""Compact analysis for downloaded Kaggriculture episode replays."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PLAYER_NAME = "KAKA Minishijie"
CHECKPOINT_DAYS = (0, 5, 10, 15, 20, 25, 29)


def _agent_name(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(agent.get("Name", agent))
    return str(agent)


def _iter_actions(action: dict[str, Any] | None) -> Iterable[list[Any]]:
    action = action or {}
    farmer = action.get("farmer")
    if farmer:
        yield farmer
    yield from (entry for entry in action.get("hands", []) if entry)
    yield from (entry for entry in action.get("market", []) if entry)


def _farm_state(observation: dict[str, Any], player_index: int) -> dict[str, Any]:
    farm = observation["farms"][player_index]
    private = observation.get("private", {})
    shed = private.get("shed", {})
    kinds: Counter[str] = Counter()
    crops: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    animal_health: Counter[str] = Counter()
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", "UNKNOWN"))
            kinds[kind] += 1
            crop = tile.get("crop")
            if crop:
                crops[str(crop)] += 1
            animal = tile.get("animal")
            if animal:
                animals[str(animal)] += 1
                if tile.get("consecutive_unfed", 0):
                    animal_health["unfed"] += 1
                if not tile.get("cared_today", False):
                    animal_health["uncared_today"] += 1
    for animal in ("GOOSE", "COW", "SHEEP"):
        animals[f"{animal}_SHED"] += int(shed.get(animal, 0) or 0)
    return {
        "money": round(float(farm.get("money", 0.0)), 3),
        "hands": len(farm.get("hands", [])),
        "unlocked_quadrants": len(farm.get("unlocked_quadrants", [])),
        "tile_kinds": dict(sorted(kinds.items())),
        "crops": dict(sorted(crops.items())),
        "animals": dict(sorted((k, v) for k, v in animals.items() if v)),
        "animal_health": dict(sorted(animal_health.items())),
        "shed": {k: v for k, v in shed.items() if v},
    }


def _summarize_player(data: dict[str, Any], player_index: int) -> dict[str, Any]:
    names = [_agent_name(agent) for agent in data["info"]["Agents"]]
    action_counts: Counter[str] = Counter()
    market_quantities: Counter[str] = Counter()
    first_step: dict[str, int] = {}
    first_day: dict[str, int] = {}
    checkpoints: dict[str, Any] = {}
    last_for_day: dict[int, dict[str, Any]] = {}

    for step_number, step in enumerate(data["steps"]):
        record = step[player_index]
        observation = record["observation"]
        day = int(observation.get("day", step_number // 24))
        last_for_day[day] = observation
        for entry in _iter_actions(record.get("action")):
            operation = str(entry[0])
            action_counts[operation] += 1
            first_step.setdefault(operation, step_number)
            first_day.setdefault(operation, day)
            if operation in {
                "BUY_SEED",
                "BUY_PRODUCT",
                "BUY_ANIMAL",
                "SELL",
            } and len(entry) >= 3:
                market_quantities[f"{operation}:{entry[1]}"] += int(entry[2])
            elif operation == "BUY_LAND":
                market_quantities["BUY_LAND"] += 1

    for day in CHECKPOINT_DAYS:
        if day in last_for_day:
            checkpoints[str(day)] = _farm_state(last_for_day[day], player_index)

    final_observation = data["steps"][-1][player_index]["observation"]
    reward = float(data["rewards"][player_index])
    return {
        "name": names[player_index],
        "reward": reward,
        "action_counts": dict(sorted(action_counts.items())),
        "market_quantities": dict(sorted(market_quantities.items())),
        "first_step": dict(sorted(first_step.items())),
        "first_day": dict(sorted(first_day.items())),
        "checkpoints": checkpoints,
        "final": _farm_state(final_observation, player_index),
    }


def summarize_episode(path: Path, player_name: str = PLAYER_NAME) -> dict[str, Any] | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    names = [_agent_name(agent) for agent in data["info"]["Agents"]]
    if player_name not in names:
        return None
    player_index = names.index(player_name)
    opponent_index = 1 - player_index
    player = _summarize_player(data, player_index)
    opponent = _summarize_player(data, opponent_index)
    return {
        "episode_id": int(path.stem.split("-")[-1]),
        "episode_uuid": data.get("id"),
        "seed": data.get("info", {}).get("seed"),
        "result": "win" if player["reward"] > opponent["reward"] else "loss",
        "margin": player["reward"] - opponent["reward"],
        "player_index": player_index,
        "player": player,
        "opponent": opponent,
    }


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def _group_summary(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, Any] = {}
    for result in ("win", "loss", "all"):
        rows = episodes if result == "all" else [e for e in episodes if e["result"] == result]
        if not rows:
            continue
        metrics: dict[str, Any] = {
            "games": len(rows),
            "player_reward_mean": _mean([e["player"]["reward"] for e in rows]),
            "opponent_reward_mean": _mean([e["opponent"]["reward"] for e in rows]),
            "margin_mean": _mean([e["margin"] for e in rows]),
        }
        for side in ("player", "opponent"):
            for day in CHECKPOINT_DAYS:
                states = [e[side]["checkpoints"].get(str(day)) for e in rows]
                states = [state for state in states if state]
                if not states:
                    continue
                prefix = f"{side}_day{day}"
                metrics[f"{prefix}_money_mean"] = _mean([float(s["money"]) for s in states])
                metrics[f"{prefix}_animals_mean"] = _mean(
                    [
                        float(sum(v for k, v in s["animals"].items() if not k.endswith("_SHED")))
                        for s in states
                    ]
                )
                metrics[f"{prefix}_crops_mean"] = _mean(
                    [float(sum(s["crops"].values())) for s in states]
                )
        grouped[result] = metrics
    return grouped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_dir", type=Path)
    parser.add_argument("--ids", nargs="*", type=int)
    parser.add_argument("--player-name", default=PLAYER_NAME)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.ids:
        paths = [args.episode_dir / f"episode-{episode_id}.json" for episode_id in args.ids]
    else:
        paths = sorted(args.episode_dir.glob("episode-*.json"))
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing episode files: " + ", ".join(missing))

    summaries = [summarize_episode(path, args.player_name) for path in paths]
    episodes = [episode for episode in summaries if episode is not None]
    episodes.sort(key=lambda row: row["episode_id"], reverse=True)
    report = {
        "player": args.player_name,
        "input_file_count": len(paths),
        "skipped_other_players": len(paths) - len(episodes),
        "episode_count": len(episodes),
        "wins": sum(e["result"] == "win" for e in episodes),
        "losses": sum(e["result"] == "loss" for e in episodes),
        "group_summary": _group_summary(episodes),
        "episodes": episodes,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "input_file_count": report["input_file_count"],
                    "skipped_other_players": report["skipped_other_players"],
                    "episode_count": report["episode_count"],
                    "wins": report["wins"],
                    "losses": report["losses"],
                    "group_summary": report["group_summary"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(payload)


if __name__ == "__main__":
    main()
