"""Evaluate replay-route selection using only the currently visible shop prefix.

The policy deliberately selects one intact replay expert at a time.  It does
not form a per-step action consensus, because that can splice incompatible
private inventories and unit positions from different games.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def common_prefix(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


@dataclass(frozen=True)
class Episode:
    episode_id: int
    seat: int
    opponent: str
    reward: float
    opponent_reward: float
    actions: tuple[str, ...]
    shops: tuple[tuple[str, ...], ...]

    @property
    def margin(self) -> float:
        return self.reward - self.opponent_reward


def load_episode(path: Path, player_name: str) -> Episode:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = [str(agent.get("Name", "")) for agent in replay["info"]["Agents"]]
    seat = names.index(player_name)
    opponent = names[1 - seat]
    actions: list[str] = []
    shops: list[tuple[str, ...]] = []
    for runtime_step in range(len(replay["steps"])):
        state = replay["steps"][runtime_step][seat]
        action_step = min(runtime_step + 1, len(replay["steps"]) - 1)
        actions.append(compact(replay["steps"][action_step][seat].get("action") or {}))
        town = (state.get("observation") or {}).get("town") or {}
        shops.append(tuple(str(item) for item in town.get("unlocked_shops") or ()))
    rewards = replay["rewards"]
    return Episode(
        episode_id=int(path.stem),
        seat=seat,
        opponent=opponent,
        reward=float(rewards[seat]),
        opponent_reward=float(rewards[1 - seat]),
        actions=tuple(actions),
        shops=tuple(shops),
    )


def select_expert(target: Episode, candidates: list[Episode], step: int) -> tuple[Episode, int]:
    prefix = target.shops[step]
    scored = [
        (common_prefix(prefix, candidate.shops[step]), candidate.reward, candidate)
        for candidate in candidates
    ]
    matched, _reward, selected = max(scored, key=lambda row: (row[0], row[1]))
    return selected, matched


def evaluate(target: Episode, candidates: list[Episode]) -> dict[str, object]:
    matches = 0
    exact_prefix_steps = 0
    first_mismatch = -1
    selected_counts: dict[int, int] = {}
    transition_points: list[dict[str, object]] = []
    previous_selected: int | None = None
    for step in range(min(len(target.actions), *(len(item.actions) for item in candidates))):
        selected, matched_prefix = select_expert(target, candidates, step)
        selected_counts[selected.episode_id] = selected_counts.get(selected.episode_id, 0) + 1
        if matched_prefix == len(target.shops[step]):
            exact_prefix_steps += 1
        if selected.actions[step] == target.actions[step]:
            matches += 1
        elif first_mismatch < 0:
            first_mismatch = step
        if previous_selected != selected.episode_id:
            transition_points.append(
                {
                    "step": step,
                    "expert": selected.episode_id,
                    "matched_shop_prefix": matched_prefix,
                    "visible_shops": list(target.shops[step]),
                }
            )
            previous_selected = selected.episode_id
    steps = min(len(target.actions), *(len(item.actions) for item in candidates))
    return {
        "episode_id": target.episode_id,
        "seat": target.seat,
        "opponent": target.opponent,
        "margin": target.margin,
        "steps": steps,
        "action_match_fraction": matches / steps,
        "exact_prefix_fraction": exact_prefix_steps / steps,
        "first_mismatch": first_mismatch,
        "selected_counts": selected_counts,
        "transitions": transition_points,
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
        "episodes": results,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
