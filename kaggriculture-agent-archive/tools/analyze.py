"""Print day-by-day diagnostics for a local Kaggriculture match."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from kaggle_environments import make


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def crop_counts(farm):
    counts = {}
    weeds = 0
    empty = 0
    for row in farm["tiles"]:
        for tile in row:
            if tile is None:
                empty += 1
            elif isinstance(tile, dict) and tile.get("kind") == "WEED":
                weeds += 1
            elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
                crop = tile["crop"]
                counts[crop] = counts.get(crop, 0) + 1
    animals = {}
    structures = {}
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("animal"):
                animal = tile["animal"]
                animals[animal] = animals.get(animal, 0) + 1
            elif tile.get("kind") in ("COOP", "PASTURE"):
                kind = tile["kind"]
                structures[kind] = structures.get(kind, 0) + 1
    return counts, animals, structures, weeds, empty


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path)
    parser.add_argument("--right", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).parent
    left = load_module((args.left or root / "main.py").resolve(), "diag_left")
    right = load_module((args.right or root / "main.py").resolve(), "diag_right")
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": args.seed}, debug=True)
    env.run([left.agent, right.agent])

    print("day player money lands crops animals structures weeds empty shed fert products")
    for step_index in list(range(0, len(env.steps), 24)) + [len(env.steps) - 1]:
        states = env.steps[step_index]
        for player in (0, 1):
            obs = states[player].observation
            farm = obs.farms[player]
            counts, animals, structures, weeds, empty = crop_counts(farm)
            private_shed = obs.private.get("shed", {})
            shed = sum(private_shed.values())
            products = sum(private_shed.get(item, 0) for item in ("EGG", "MILK", "WOOL"))
            print(
                f"{obs.day:>3} {player:>6} {farm['money']:>7.0f} "
                f"{len(farm['unlocked_quadrants']):>5} {str(counts):<28} "
                f"{str(animals):<25} {str(structures):<18} {weeds:>5} {empty:>5} "
                f"{shed:>4} {private_shed.get('FERTILIZER', 0):>4} {products:>8}"
            )


if __name__ == "__main__":
    main()
