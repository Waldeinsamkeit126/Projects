"""Deterministic cross-play benchmark for Kaggriculture agents.

Unlike replay_evaluate.py, this benchmark runs both agents closed-loop.  Every
unordered pair plays both seats on fixed development and holdout seed sets.
The resulting report records agent hashes, seed provenance, seat-stratified
metrics, and a seed-block bootstrap interval for the win-point rate.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib.util
import inspect
import itertools
import json
from pathlib import Path
import random
import statistics
import sys
import time
from typing import Any


DEPS = Path(__file__).resolve().parents[1] / "deps"
sys.path.insert(0, str(DEPS))

from kaggle_environments import make


def _load_agent(path_text: str, role: str):
    path = Path(path_text).resolve()
    digest = hashlib.sha1(f"{path}:{role}:{time.time_ns()}".encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(f"benchmark_{role}_{digest}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load agent: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def _play_task(task: dict[str, Any]) -> dict[str, Any]:
    agent_a = _load_agent(task["path_a"], "a")
    agent_b = _load_agent(task["path_b"], "b")
    position_a = int(task["position_a"])
    times_a: list[float] = []
    times_b: list[float] = []

    def timed(agent, timings):
        accepts_configuration = len(inspect.signature(agent).parameters) >= 2

        def wrapped(obs, configuration=None):
            started = time.perf_counter()
            action = (
                agent(obs, configuration)
                if accepts_configuration
                else agent(obs)
            )
            timings.append(time.perf_counter() - started)
            return action

        return wrapped

    players = [timed(agent_a, times_a), timed(agent_b, times_b)]
    if position_a == 1:
        players.reverse()
    configuration = {"episodeSteps": 720, "seed": int(task["seed"])}
    if task.get("town_center_sell_interval") is not None:
        configuration["townCenterSellInterval"] = int(
            task["town_center_sell_interval"]
        )
    env = make("kaggriculture", configuration=configuration, debug=True)
    started = time.perf_counter()
    env.run(players)
    elapsed = time.perf_counter() - started
    rewards = [float(state.reward or 0.0) for state in env.steps[-1]]
    statuses = [str(state.status) for state in env.steps[-1]]
    score_a = rewards[position_a]
    score_b = rewards[1 - position_a]
    return {
        "split": task["split"],
        "seed": int(task["seed"]),
        "agent_a": task["agent_a"],
        "agent_b": task["agent_b"],
        "position_a": position_a,
        "score_a": score_a,
        "score_b": score_b,
        "margin_a": score_a - score_b,
        "winner": task["agent_a"] if score_a > score_b else task["agent_b"] if score_b > score_a else None,
        "elapsed_seconds": elapsed,
        "max_action_seconds_a": max(times_a, default=0.0),
        "max_action_seconds_b": max(times_b, default=0.0),
        "statuses": statuses,
    }


def _parse_seeds(text: str) -> list[int]:
    values: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError(f"Invalid seed range: {part}")
            values.extend(range(start, end + 1))
        else:
            values.append(int(part))
    if not values:
        raise ValueError("At least one seed is required")
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate seeds: {text}")
    return values


def _parse_agents(items: list[str]) -> dict[str, str]:
    agents: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Agent must be NAME=PATH: {item}")
        name, path_text = item.split("=", 1)
        name = name.strip()
        path = Path(path_text).resolve()
        if not name or name in agents:
            raise ValueError(f"Missing or duplicate agent name: {name!r}")
        if not path.is_file():
            raise FileNotFoundError(path)
        agents[name] = str(path)
    if len(agents) < 2:
        raise ValueError("At least two agents are required")
    return agents


def _sha256(path_text: str) -> str:
    return hashlib.sha256(Path(path_text).read_bytes()).hexdigest()


def _agent_view(game: dict[str, Any], name: str) -> dict[str, Any]:
    if game["agent_a"] == name:
        opponent = game["agent_b"]
        score = game["score_a"]
        opponent_score = game["score_b"]
        margin = game["margin_a"]
        position = game["position_a"]
        action_time = game["max_action_seconds_a"]
    else:
        opponent = game["agent_a"]
        score = game["score_b"]
        opponent_score = game["score_a"]
        margin = -game["margin_a"]
        position = 1 - game["position_a"]
        action_time = game["max_action_seconds_b"]
    return {
        "split": game["split"],
        "seed": game["seed"],
        "opponent": opponent,
        "position": position,
        "score": score,
        "opponent_score": opponent_score,
        "margin": margin,
        "point": 1.0 if margin > 0 else 0.5 if margin == 0 else 0.0,
        "max_action_seconds": action_time,
        "all_done": all(status == "DONE" for status in game["statuses"]),
    }


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    return statistics.mean(float(row[key]) for row in rows) if rows else 0.0


def _bootstrap_seed_ci(rows: list[dict[str, Any]], samples: int = 2000) -> list[float]:
    by_seed: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_seed.setdefault(int(row["seed"]), []).append(row)
    seeds = sorted(by_seed)
    if len(seeds) < 2:
        point = _mean(rows, "point")
        return [point, point]
    rng = random.Random(20260807)
    estimates = []
    for _ in range(samples):
        sampled_rows: list[dict[str, Any]] = []
        for seed in rng.choices(seeds, k=len(seeds)):
            sampled_rows.extend(by_seed[seed])
        estimates.append(_mean(sampled_rows, "point"))
    estimates.sort()
    return [estimates[int(samples * 0.025)], estimates[int(samples * 0.975) - 1]]


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "games": len(rows),
        "wins": sum(row["point"] == 1.0 for row in rows),
        "ties": sum(row["point"] == 0.5 for row in rows),
        "losses": sum(row["point"] == 0.0 for row in rows),
        "win_point_rate": _mean(rows, "point"),
        "win_point_rate_seed_bootstrap_95ci": _bootstrap_seed_ci(rows),
        "mean_score": _mean(rows, "score"),
        "mean_margin": _mean(rows, "margin"),
        "median_margin": statistics.median(row["margin"] for row in rows) if rows else 0.0,
        "min_margin": min((row["margin"] for row in rows), default=0.0),
        "max_action_seconds": max((row["max_action_seconds"] for row in rows), default=0.0),
        "all_done": all(row["all_done"] for row in rows),
        "by_position": {
            str(position): {
                "games": len(seat_rows),
                "win_point_rate": _mean(seat_rows, "point"),
                "mean_score": _mean(seat_rows, "score"),
                "mean_margin": _mean(seat_rows, "margin"),
            }
            for position in (0, 1)
            if (seat_rows := [row for row in rows if row["position"] == position])
        },
    }


def _build_report(
    agents: dict[str, str],
    dev_seeds: list[int],
    holdout_seeds: list[int],
    games: list[dict[str, Any]],
    town_center_sell_interval: int | None,
) -> dict[str, Any]:
    names = list(agents)
    views = {
        name: [_agent_view(game, name) for game in games if name in (game["agent_a"], game["agent_b"])]
        for name in names
    }
    agent_summaries: dict[str, Any] = {}
    for name, rows in views.items():
        agent_summaries[name] = {
            split: _summarize_rows([row for row in rows if row["split"] == split])
            for split in ("dev", "holdout")
        }

    pair_summaries = []
    for name_a, name_b in itertools.combinations(names, 2):
        pair_games = [
            game for game in games
            if {game["agent_a"], game["agent_b"]} == {name_a, name_b}
        ]
        pair_summaries.append(
            {
                "agent_a": name_a,
                "agent_b": name_b,
                "splits": {
                    split: _summarize_rows(
                        [
                            _agent_view(game, name_a)
                            for game in pair_games
                            if game["split"] == split
                        ]
                    )
                    for split in ("dev", "holdout")
                },
            }
        )

    ranking = {
        split: sorted(
            (
                {
                    "agent": name,
                    "win_point_rate": agent_summaries[name][split]["win_point_rate"],
                    "mean_margin": agent_summaries[name][split]["mean_margin"],
                    "mean_score": agent_summaries[name][split]["mean_score"],
                }
                for name in names
            ),
            key=lambda row: (row["win_point_rate"], row["mean_margin"], row["mean_score"]),
            reverse=True,
        )
        for split in ("dev", "holdout")
    }
    return {
        "provenance": {
            "benchmark": str(Path(__file__).resolve()),
            "closed_loop": True,
            "episode_steps": 720,
            "town_center_sell_interval": town_center_sell_interval,
            "dev_seeds": dev_seeds,
            "holdout_seeds": holdout_seeds,
            "agents": {
                name: {"path": path, "sha256": _sha256(path)} for name, path in agents.items()
            },
        },
        "ranking": ranking,
        "agents": agent_summaries,
        "pairs": pair_summaries,
        "games": sorted(
            games,
            key=lambda row: (
                row["split"], row["agent_a"], row["agent_b"], row["seed"], row["position_a"]
            ),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--dev-seeds", default="0-3")
    parser.add_argument("--holdout-seeds", default="1000-1003")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--town-center-sell-interval",
        type=int,
        help="Override the environment's townCenterSellInterval.",
    )
    parser.add_argument(
        "--pair",
        action="append",
        nargs=2,
        metavar=("AGENT_A", "AGENT_B"),
        help="Run only this pair; repeat for a fixed candidate-versus-pool benchmark.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    agents = _parse_agents(args.agent)
    dev_seeds = _parse_seeds(args.dev_seeds)
    holdout_seeds = _parse_seeds(args.holdout_seeds)
    if set(dev_seeds) & set(holdout_seeds):
        raise ValueError("Development and holdout seeds must be disjoint")

    if args.pair:
        pair_names = []
        seen_pairs = set()
        for raw_a, raw_b in args.pair:
            if raw_a not in agents or raw_b not in agents:
                raise ValueError(f"Unknown agent pair: {raw_a}, {raw_b}")
            if raw_a == raw_b:
                raise ValueError(f"Self pair is not allowed: {raw_a}")
            key = frozenset((raw_a, raw_b))
            if key in seen_pairs:
                raise ValueError(f"Duplicate pair: {raw_a}, {raw_b}")
            seen_pairs.add(key)
            pair_names.append((raw_a, raw_b))
    else:
        pair_names = list(itertools.combinations(agents, 2))

    tasks = []
    for name_a, name_b in pair_names:
        for split, seeds in (("dev", dev_seeds), ("holdout", holdout_seeds)):
            for seed in seeds:
                for position_a in (0, 1):
                    tasks.append(
                        {
                            "split": split,
                            "seed": seed,
                            "agent_a": name_a,
                            "agent_b": name_b,
                            "path_a": agents[name_a],
                            "path_b": agents[name_b],
                            "position_a": position_a,
                            "town_center_sell_interval": args.town_center_sell_interval,
                        }
                    )

    print(
        f"Running {len(tasks)} closed-loop games across {len(agents)} agents "
        f"with {args.workers} workers...",
        flush=True,
    )
    games = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(_play_task, task) for task in tasks]
        for index, future in enumerate(as_completed(futures), 1):
            game = future.result()
            games.append(game)
            print(
                f"[{index:03d}/{len(tasks)}] {game['split']} seed={game['seed']} "
                f"{game['agent_a']}@{game['position_a']} vs {game['agent_b']} "
                f"margin={game['margin_a']:+.0f}",
                flush=True,
            )

    report = _build_report(
        agents,
        dev_seeds,
        holdout_seeds,
        games,
        args.town_center_sell_interval,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("\nHoldout ranking:")
    for index, row in enumerate(report["ranking"]["holdout"], 1):
        print(
            f"{index}. {row['agent']}: points={row['win_point_rate']:.3f} "
            f"margin={row['mean_margin']:+.1f} score={row['mean_score']:.1f}"
        )
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
