"""Local multi-seed evaluation for the Kaggriculture submission agent."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time

DEPS = Path(__file__).resolve().parents[1] / "deps"
sys.path.insert(0, str(DEPS))

from kaggle_environments import make


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def configure_variant(module, variant: str):
    if variant == "production":
        return module.agent
    if variant in ("goose_bias", "cow45", "cow_bias", "cow65", "sheep_bias"):
        module.ANIMAL_BASE_WEIGHTS = {
            "goose_bias": {"GOOSE": 0.55, "COW": 0.25, "SHEEP": 0.20},
            "cow45": {"GOOSE": 0.25, "COW": 0.45, "SHEEP": 0.30},
            "cow_bias": {"GOOSE": 0.20, "COW": 0.55, "SHEEP": 0.25},
            "cow65": {"GOOSE": 0.15, "COW": 0.65, "SHEEP": 0.20},
            "sheep_bias": {"GOOSE": 0.20, "COW": 0.25, "SHEEP": 0.55},
        }[variant]
        return module.agent
    if variant in (
        "herd35", "herd45", "herd75", "herd_fast", "herd_slow",
        "herd_slow35", "herd_slow45", "herd_mid45", "herd_strict",
    ):
        if variant in ("herd35", "herd_slow35"):
            module.ANIMAL_SHARE = 0.35
        elif variant in ("herd45", "herd_slow45", "herd_mid45"):
            module.ANIMAL_SHARE = 0.45
        elif variant == "herd75":
            module.ANIMAL_SHARE = 0.75
        if variant == "herd_fast":
            module.ANIMAL_RAMP_PER_DAY = 1.6
        if variant in ("herd_slow", "herd_slow35", "herd_slow45"):
            module.ANIMAL_START = 5.0
            module.ANIMAL_RAMP_PER_DAY = 0.75
        if variant == "herd_mid45":
            module.ANIMAL_START = 6.0
            module.ANIMAL_RAMP_PER_DAY = 0.60
        if variant == "herd_strict":
            module.ANIMAL_STOP_HEALTH = 0.68
            module.ANIMAL_SLOW_HEALTH = 0.90
        return module.agent
    if variant == "balanced":
        def balanced_weights(day):
            if day <= 12:
                return {
                    "MELON": 0.32, "STRAWBERRY": 0.12, "TOMATO": 0.16,
                    "CARROT": 0.20, "WHEAT": 0.20,
                }
            if day <= 18:
                return {"MELON": 0.26, "TOMATO": 0.18, "CARROT": 0.29, "WHEAT": 0.27}
            if day <= 26:
                return {"CARROT": 0.54, "WHEAT": 0.46}
            return {}
        module._phase_weights = balanced_weights
        module.SELL_CAP["MELON"] = 6
    elif variant in (
        "melon", "melon50", "melon70", "melon_fast", "melon18", "melon24",
        "melon_all", "melon_slow",
    ):
        melon_share = {"melon50": 0.50, "melon70": 0.70}.get(variant, 0.62)
        def melon_weights(day):
            if day <= 18:
                remainder = 1.0 - melon_share
                return {
                    "MELON": melon_share,
                    "CARROT": remainder * 0.42,
                    "WHEAT": remainder * 0.37,
                    "TOMATO": remainder * 0.21,
                }
            if day <= 26:
                return {"CARROT": 0.55, "WHEAT": 0.45}
            return {}
        module._phase_weights = melon_weights
        if variant in ("melon", "melon50", "melon70"):
            module.SELL_CAP["MELON"] = 6
        elif variant == "melon_fast":
            module.SELL_CAP["MELON"] = 12
        elif variant == "melon18":
            module.SELL_CAP["MELON"] = 18
        elif variant == "melon24":
            module.SELL_CAP["MELON"] = 24
        elif variant == "melon_all":
            module.SELL_CAP["MELON"] = 100
        elif variant == "melon_slow":
            module.SELL_CAP["MELON"] = 3
    elif variant == "adaptive_melon":
        def adaptive_melon_weights(day):
            if day <= 18:
                return {"MELON": 0.70, "CARROT": 0.12, "WHEAT": 0.10, "TOMATO": 0.08}
            if day <= 26:
                return {"CARROT": 0.55, "WHEAT": 0.45}
            return {}
        module._phase_weights = adaptive_melon_weights
        module.CROWD_RISK["MELON"] = 0.8
    elif variant == "hypermelon":
        def hypermelon_weights(day):
            if day <= 18:
                return {"MELON": 0.86, "CARROT": 0.07, "WHEAT": 0.07}
            if day <= 26:
                return {"CARROT": 0.55, "WHEAT": 0.45}
            return {}
        module._phase_weights = hypermelon_weights
        module.CROWD_RISK["MELON"] = 0.15
    elif variant == "robust":
        def robust_weights(day):
            if day <= 18:
                return {"CARROT": 0.34, "WHEAT": 0.32, "TOMATO": 0.22, "MELON": 0.12}
            if day <= 26:
                return {"CARROT": 0.56, "WHEAT": 0.44}
            return {}
        module._phase_weights = robust_weights
    elif variant == "dump":
        module.SELL_CAP.update({name: 100 for name in module.SELL_CAP})
    else:
        raise ValueError(f"unknown variant: {variant}")
    return module.agent


def play(candidate, opponent, seed: int, candidate_position: int):
    action_times = []

    def timed_candidate(obs):
        started = time.perf_counter()
        result = candidate(obs)
        action_times.append(time.perf_counter() - started)
        return result

    agents = [timed_candidate, opponent]
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
    ours = rewards[candidate_position]
    theirs = rewards[1 - candidate_position]
    return {
        "seed": seed,
        "position": candidate_position,
        "ours": ours,
        "theirs": theirs,
        "margin": ours - theirs,
        "win": ours > theirs,
        "tie": ours == theirs,
        "elapsed_seconds": elapsed,
        "max_action_seconds": max(action_times, default=0.0),
        "statuses": statuses,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path(__file__).with_name("main.py"))
    variants = (
        "goose_bias", "cow45", "cow_bias", "cow65", "sheep_bias",
        "herd35", "herd45", "herd75", "herd_fast", "herd_slow", "herd_slow35",
        "herd_slow45", "herd_mid45", "herd_strict",
        "production", "balanced", "melon", "melon50", "melon70", "melon_fast", "melon18",
        "melon24", "melon_all", "melon_slow",
        "adaptive_melon", "hypermelon", "robust", "dump",
    )
    parser.add_argument("--candidate-variant", choices=variants, default="production")
    parser.add_argument("--opponent", choices=("starter", "random", "self", *variants), default="starter")
    parser.add_argument("--opponent-agent", type=Path)
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    candidate_module = load_module(args.agent.resolve(), "candidate_agent")
    candidate = configure_variant(candidate_module, args.candidate_variant)
    if args.opponent_agent:
        opponent_module = load_module(args.opponent_agent.resolve(), "external_opponent")
        opponent = opponent_module.agent
    elif args.opponent == "self":
        opponent_module = load_module(args.agent.resolve(), "self_opponent")
        opponent = configure_variant(opponent_module, args.candidate_variant)
    elif args.opponent in variants:
        opponent_module = load_module(args.agent.resolve(), f"{args.opponent}_opponent")
        opponent = configure_variant(opponent_module, args.opponent)
    else:
        opponent = args.opponent
    results = []
    for seed in range(args.seeds):
        for position in (0, 1):
            result = play(candidate, opponent, seed, position)
            results.append(result)
            print(
                f"seed={seed:02d} pos={position} "
                f"ours={result['ours']:.0f} theirs={result['theirs']:.0f} "
                f"margin={result['margin']:+.0f} t={result['elapsed_seconds']:.2f}s "
                f"max_action={result['max_action_seconds'] * 1000:.1f}ms"
            )

    summary = {
        "candidate_variant": args.candidate_variant,
        "opponent": args.opponent,
        "games": len(results),
        "wins": sum(r["win"] for r in results),
        "ties": sum(r["tie"] for r in results),
        "win_rate": sum(r["win"] for r in results) / len(results),
        "mean_score": statistics.mean(r["ours"] for r in results),
        "mean_opponent_score": statistics.mean(r["theirs"] for r in results),
        "mean_margin": statistics.mean(r["margin"] for r in results),
        "median_margin": statistics.median(r["margin"] for r in results),
        "max_game_seconds": max(r["elapsed_seconds"] for r in results),
        "max_action_seconds": max(r["max_action_seconds"] for r in results),
    }
    print(json.dumps(summary, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"summary": summary, "games": results}, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
