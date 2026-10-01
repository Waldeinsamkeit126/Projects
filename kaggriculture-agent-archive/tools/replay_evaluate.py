"""Evaluate a candidate against open-loop actions from online opponents.

The original seed and player position are preserved.  This is exact for the
uploaded agent when the local environment matches Kaggle, and a useful
counterfactual benchmark for nearby candidate changes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

DEPS = Path(__file__).resolve().parents[1] / "deps"
sys.path.insert(0, str(DEPS))

from kaggle_environments import make


PLAYER_NAME = "KAKA Minishijie"


def _agent_name(agent: Any) -> str:
    if isinstance(agent, dict):
        return str(agent.get("Name", agent))
    return str(agent)


def load_agent(path: Path):
    module_name = f"candidate_{abs(hash(path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.agent


def pass_action() -> dict[str, Any]:
    return {"farmer": ["PASS"], "hands": [], "market": []}


def play(candidate, episode_path: Path) -> dict[str, Any]:
    replay = json.loads(episode_path.read_text(encoding="utf-8"))
    names = [_agent_name(agent) for agent in replay["info"]["Agents"]]
    candidate_position = names.index(PLAYER_NAME)
    opponent_position = 1 - candidate_position
    # kaggle-environments stores the action that produced step N on step N,
    # while agents receive the observation from step N-1.  Shift by one so
    # observation.step=0 replays the action recorded on replay step 1.
    recorded_actions = [
        step[opponent_position].get("action") or pass_action()
        for step in replay["steps"][1:]
    ]
    seed = int(replay["info"]["seed"])
    action_times: list[float] = []

    def timed_candidate(obs):
        started = time.perf_counter()
        action = candidate(obs)
        action_times.append(time.perf_counter() - started)
        return action

    def replay_opponent(obs):
        step = int(obs.get("step", 0) if isinstance(obs, dict) else getattr(obs, "step", 0))
        if 0 <= step < len(recorded_actions):
            return recorded_actions[step]
        return pass_action()

    agents = [timed_candidate, replay_opponent]
    if candidate_position == 1:
        agents.reverse()
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 720, "seed": seed},
        debug=True,
    )
    started = time.perf_counter()
    env.run(agents)
    elapsed = time.perf_counter() - started
    rewards = [float(state.reward or 0.0) for state in env.steps[-1]]
    statuses = [state.status for state in env.steps[-1]]
    original_rewards = [float(value) for value in replay["rewards"]]
    ours = rewards[candidate_position]
    theirs = rewards[opponent_position]
    original_ours = original_rewards[candidate_position]
    original_theirs = original_rewards[opponent_position]
    return {
        "episode_id": int(episode_path.stem.split("-")[-1]),
        "opponent": names[opponent_position],
        "seed": seed,
        "position": candidate_position,
        "ours": ours,
        "theirs": theirs,
        "margin": ours - theirs,
        "win": ours > theirs,
        "original_ours": original_ours,
        "original_theirs": original_theirs,
        "original_margin": original_ours - original_theirs,
        "score_delta": ours - original_ours,
        "margin_delta": (ours - theirs) - (original_ours - original_theirs),
        "elapsed_seconds": elapsed,
        "max_action_seconds": max(action_times, default=0.0),
        "statuses": statuses,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    candidate = load_agent(args.agent)
    results = []
    for episode_id in args.ids:
        result = play(candidate, args.episode_dir / f"episode-{episode_id}.json")
        results.append(result)
        print(
            f"episode={episode_id} opp={result['opponent']} "
            f"score={result['ours']:.0f} margin={result['margin']:+.0f} "
            f"delta={result['score_delta']:+.0f} "
            f"margin_delta={result['margin_delta']:+.0f} "
            f"status={result['statuses']}"
        )

    summary = {
        "agent": str(args.agent),
        "games": len(results),
        "wins": sum(result["win"] for result in results),
        "mean_score": statistics.mean(result["ours"] for result in results),
        "mean_margin": statistics.mean(result["margin"] for result in results),
        "mean_score_delta": statistics.mean(result["score_delta"] for result in results),
        "mean_margin_delta": statistics.mean(result["margin_delta"] for result in results),
        "median_margin_delta": statistics.median(result["margin_delta"] for result in results),
        "max_action_seconds": max(result["max_action_seconds"] for result in results),
        "all_done": all(status == "DONE" for result in results for status in result["statuses"]),
    }
    print(json.dumps(summary, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"summary": summary, "games": results}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
