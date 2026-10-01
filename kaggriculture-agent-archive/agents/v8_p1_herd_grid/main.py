"""Local V8 replay grid for seat-1 herd weights; configured by environment."""

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASE_PATH = (
    ROOT
    / "outputs"
    / "kaggriculture_agent"
    / "v7_purecrop81_after_probe"
    / "main.py"
)
SPEC = spec_from_file_location("kaggriculture_v7_base_herd_grid", BASE_PATH)
BASE = module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

P1_WEIGHTS = {
    "GOOSE": float(os.environ.get("KAG_P1_GOOSE", "0.08")),
    "COW": float(os.environ.get("KAG_P1_COW", "0.55")),
    "SHEEP": float(os.environ.get("KAG_P1_SHEEP", "0.37")),
}
P1_CROWD_PENALTY = float(os.environ.get("KAG_P1_CROWD", "0.06"))
_original_desired_animal_counts = BASE._desired_animal_counts


def _desired_animal_counts(obs, farm, opponent):
    if int(BASE._get(obs, "player", 0)) != 1:
        return _original_desired_animal_counts(obs, farm, opponent)

    old_weights = BASE.ANIMAL_BASE_WEIGHTS
    old_penalty = BASE.ANIMAL_CROWD_PENALTY
    try:
        BASE.ANIMAL_BASE_WEIGHTS = P1_WEIGHTS
        BASE.ANIMAL_CROWD_PENALTY = P1_CROWD_PENALTY
        return _original_desired_animal_counts(obs, farm, opponent)
    finally:
        BASE.ANIMAL_BASE_WEIGHTS = old_weights
        BASE.ANIMAL_CROWD_PENALTY = old_penalty


BASE._desired_animal_counts = _desired_animal_counts


def agent(obs):
    return BASE.agent(obs)

