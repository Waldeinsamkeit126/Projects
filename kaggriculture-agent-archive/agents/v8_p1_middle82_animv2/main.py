"""Local V8 experiment: V7 with seat-1 V4 crop and herd parameters."""

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
SPEC = spec_from_file_location("kaggriculture_v7_base_middle82", BASE_PATH)
BASE = module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

_original_phase_weights = BASE._phase_weights
_original_desired_animal_counts = BASE._desired_animal_counts


def _phase_weights(day, step, opponent, player_index):
    if player_index == 1 and day <= 17:
        if step == 0:
            BASE.USE_MELON_PRESSURE = None
            BASE.USE_P0_PURE_CROP_MIDDLE = None
        return {"MELON": 0.82, "CARROT": 0.08, "WHEAT": 0.10}
    return _original_phase_weights(day, step, opponent, player_index)


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


BASE._phase_weights = _phase_weights
BASE._desired_animal_counts = _desired_animal_counts


def agent(obs):
    return BASE.agent(obs)

