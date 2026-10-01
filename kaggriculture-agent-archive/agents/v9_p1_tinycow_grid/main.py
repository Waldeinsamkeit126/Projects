"""Local grid wrapper for the V8 seat-one tiny-cow crop branch."""

import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASE_PATH = (
    ROOT
    / "outputs"
    / "kaggriculture_agent"
    / "v8_p1_crowd07"
    / "main.py"
)
SPEC = spec_from_file_location("kaggriculture_v8_tinycow_grid_base", BASE_PATH)
BASE = module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

TINY_COW_MELON = float(os.environ.get("KAG_TINYCOW_MELON", "0.78"))
TINY_COW_CARROT = 0.08
TINY_COW_WHEAT = 1.0 - TINY_COW_MELON - TINY_COW_CARROT

_original_phase_weights = BASE._phase_weights
_use_tiny_cow_mix = None


def _phase_weights(day, step, opponent, player_index):
    global _use_tiny_cow_mix

    if step == 0:
        _use_tiny_cow_mix = None

    weights = _original_phase_weights(day, step, opponent, player_index)
    if player_index != 1 or day > 17:
        return weights

    if _use_tiny_cow_mix is None and day >= 1:
        crops = BASE._plant_counts(opponent)
        animals, _ = BASE._animal_counts(opponent)
        _use_tiny_cow_mix = (
            animals.get("COW", 0) >= 3 and sum(crops.values()) <= 1
        )

    if _use_tiny_cow_mix:
        return {
            "MELON": TINY_COW_MELON,
            "CARROT": TINY_COW_CARROT,
            "WHEAT": TINY_COW_WHEAT,
        }
    return weights


BASE._phase_weights = _phase_weights


def agent(obs):
    return BASE.agent(obs)

