"""Local V8 experiment: keep V7 crops, restore V4 herd tuning in seat 1."""

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
SPEC = spec_from_file_location("kaggriculture_v7_base_animv2", BASE_PATH)
BASE = module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

_original_desired_animal_counts = BASE._desired_animal_counts


def _desired_animal_counts(obs, farm, opponent):
    if int(BASE._get(obs, "player", 0)) != 1:
        return _original_desired_animal_counts(obs, farm, opponent)

    old_weights = BASE.ANIMAL_BASE_WEIGHTS
    old_penalty = BASE.ANIMAL_CROWD_PENALTY
    try:
        BASE.ANIMAL_BASE_WEIGHTS = {"GOOSE": 0.15, "COW": 0.50, "SHEEP": 0.35}
        BASE.ANIMAL_CROWD_PENALTY = 0.10
        return _original_desired_animal_counts(obs, farm, opponent)
    finally:
        BASE.ANIMAL_BASE_WEIGHTS = old_weights
        BASE.ANIMAL_CROWD_PENALTY = old_penalty


BASE._desired_animal_counts = _desired_animal_counts


def agent(obs):
    return BASE.agent(obs)

