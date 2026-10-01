"""Leave-one-replay-out evaluation for a compact state-aware replay policy."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


ITEMS = (
    "WHEAT",
    "MELON",
    "STRAWBERRY",
    "CARROT",
    "TOMATO",
    "MILK",
    "WOOL",
    "FERTILIZER",
    "EGG",
)
CROPS = ITEMS[:5]
ANIMALS = ("COW", "SHEEP", "GOOSE")
KINDS = ("PASTURE", "COOP", "WEED")


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def common_prefix(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def position_count(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    if not value:
        return 0
    return len(str(value).split("  "))


def signature(observation: dict[str, object], seat: int) -> tuple[float, ...]:
    farms = observation.get("farms") or []
    farm = farms[seat]
    counts = {name: 0 for name in (*CROPS, *ANIMALS, *KINDS)}
    uncared = unfed = 0
    for row in farm.get("tiles") or ():
        for tile in row or ():
            if not isinstance(tile, dict):
                continue
            crop = str(tile.get("crop") or "")
            animal = str(tile.get("animal") or "")
            kind = str(tile.get("kind") or "")
            if crop in counts:
                counts[crop] += 1
            if animal in counts:
                counts[animal] += 1
            if kind in counts:
                counts[kind] += 1
            if animal:
                unfed += int(not bool(tile.get("fed", True)))
                uncared += int(not bool(tile.get("cared_for", True)))

    private = observation.get("private") or {}
    shed = private.get("shed") or {}
    seeds = private.get("seeds") or {}
    market = observation.get("market") or {}
    prices = market.get("prices") or {}
    inventory = market.get("inventory") or {}
    quadrants = farm.get("unlocked_quadrants") or ()
    if isinstance(quadrants, str):
        quadrants = quadrants.split()

    opponent = farms[1 - seat]
    opponent_counts = {name: 0 for name in (*CROPS, *ANIMALS, *KINDS)}
    opponent_uncared = opponent_unfed = 0
    for row in opponent.get("tiles") or ():
        for tile in row or ():
            if not isinstance(tile, dict):
                continue
            crop = str(tile.get("crop") or "")
            animal = str(tile.get("animal") or "")
            kind = str(tile.get("kind") or "")
            if crop in opponent_counts:
                opponent_counts[crop] += 1
            if animal in opponent_counts:
                opponent_counts[animal] += 1
            if kind in opponent_counts:
                opponent_counts[kind] += 1
            if animal:
                opponent_unfed += int(not bool(tile.get("fed", True)))
                opponent_uncared += int(not bool(tile.get("cared_for", True)))
    opponent_quadrants = opponent.get("unlocked_quadrants") or ()
    if isinstance(opponent_quadrants, str):
        opponent_quadrants = opponent_quadrants.split()
    return (
        float(farm.get("money") or 0) / 100.0,
        float(position_count(farm.get("hands"))) * 20.0,
        float(len(quadrants)) * 50.0,
        float(farm.get("hires_today") or 0) * 10.0,
        *(float(counts[name]) * 8.0 for name in CROPS),
        *(float(counts[name]) * 15.0 for name in ANIMALS),
        *(float(counts[name]) * 8.0 for name in KINDS),
        float(unfed) * 6.0,
        float(uncared) * 4.0,
        *(float(shed.get(name) or 0) * 3.0 for name in ITEMS),
        *(float(seeds.get(name) or 0) * 3.0 for name in CROPS),
        *(float(prices.get(name) or 0) / 10.0 for name in ITEMS),
        *(float(inventory.get(name) or 0) / 10.0 for name in ITEMS),
        float(opponent.get("money") or 0) / 100.0,
        float(position_count(opponent.get("hands"))) * 20.0,
        float(len(opponent_quadrants)) * 50.0,
        float(opponent.get("hires_today") or 0) * 10.0,
        *(float(opponent_counts[name]) * 8.0 for name in CROPS),
        *(float(opponent_counts[name]) * 15.0 for name in ANIMALS),
        *(float(opponent_counts[name]) * 8.0 for name in KINDS),
        float(opponent_unfed) * 6.0,
        float(opponent_uncared) * 4.0,
    )


def distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(abs(a - b) for a, b in zip(left, right))


@dataclass(frozen=True)
class Episode:
    episode_id: int
    seat: int
    opponent: str
    reward: float
    opponent_reward: float
    actions: tuple[str, ...]
    shops: tuple[tuple[str, ...], ...]
    signatures: tuple[tuple[float, ...], ...]

    @property
    def margin(self) -> float:
        return self.reward - self.opponent_reward


def load_episode(path: Path, player_name: str) -> Episode:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = [str(agent.get("Name", "")) for agent in replay["info"]["Agents"]]
    seat = names.index(player_name)
    actions: list[str] = []
    shops: list[tuple[str, ...]] = []
    signatures: list[tuple[float, ...]] = []
    for runtime_step in range(len(replay["steps"])):
        state = replay["steps"][runtime_step][seat]
        observation = state.get("observation") or {}
        action_step = min(runtime_step + 1, len(replay["steps"]) - 1)
        actions.append(compact(replay["steps"][action_step][seat].get("action") or {}))
        town = observation.get("town") or {}
        shops.append(tuple(str(item) for item in town.get("unlocked_shops") or ()))
        signatures.append(signature(observation, seat))
    rewards = replay["rewards"]
    return Episode(
        episode_id=int(path.stem),
        seat=seat,
        opponent=names[1 - seat],
        reward=float(rewards[seat]),
        opponent_reward=float(rewards[1 - seat]),
        actions=tuple(actions),
        shops=tuple(shops),
        signatures=tuple(signatures),
    )


def select_expert(target: Episode, candidates: list[Episode], step: int) -> tuple[Episode, int, float]:
    shops = target.shops[step]
    state = target.signatures[step]
    ranked = [
        (
            common_prefix(shops, candidate.shops[step]),
            -distance(state, candidate.signatures[step]),
            candidate.reward,
            candidate,
        )
        for candidate in candidates
    ]
    matched, negative_distance, _reward, selected = max(ranked, key=lambda row: row[:3])
    return selected, matched, -negative_distance


def evaluate(target: Episode, candidates: list[Episode]) -> dict[str, object]:
    matches = exact_prefix_steps = 0
    first_mismatch = -1
    distances: list[float] = []
    selected_counts: dict[int, int] = {}
    steps = min(len(target.actions), *(len(item.actions) for item in candidates))
    for step in range(steps):
        selected, matched_prefix, state_distance = select_expert(target, candidates, step)
        selected_counts[selected.episode_id] = selected_counts.get(selected.episode_id, 0) + 1
        distances.append(state_distance)
        if matched_prefix == len(target.shops[step]):
            exact_prefix_steps += 1
        if selected.actions[step] == target.actions[step]:
            matches += 1
        elif first_mismatch < 0:
            first_mismatch = step
    return {
        "episode_id": target.episode_id,
        "seat": target.seat,
        "opponent": target.opponent,
        "margin": target.margin,
        "steps": steps,
        "action_match_fraction": matches / steps,
        "exact_prefix_fraction": exact_prefix_steps / steps,
        "mean_state_distance": sum(distances) / len(distances),
        "first_mismatch": first_mismatch,
        "selected_counts": selected_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_directory", type=Path)
    parser.add_argument("--player", default="カワシギ")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    episodes = [load_episode(path, args.player) for path in sorted(args.episode_directory.glob("*.json"))]
    results = []
    for target in episodes:
        candidates = [episode for episode in episodes if episode.seat == target.seat and episode is not target]
        results.append(evaluate(target, candidates))
    payload = {
        "player": args.player,
        "episode_count": len(episodes),
        "mean_action_match_fraction": sum(row["action_match_fraction"] for row in results) / len(results),
        "mean_exact_prefix_fraction": sum(row["exact_prefix_fraction"] for row in results) / len(results),
        "mean_state_distance": sum(row["mean_state_distance"] for row in results) / len(results),
        "episodes": results,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
