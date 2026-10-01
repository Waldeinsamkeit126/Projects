"""Local V8 experiment: keep V7, but use an 82/8/10 crop mix from seat 1.

This wrapper is for counterfactual replay evaluation only.  A validated Kaggle
submission will be flattened back to one dependency-free ``main.py``.
"""

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
SPEC = spec_from_file_location("kaggriculture_v7_base", BASE_PATH)
BASE = module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

_original_phase_weights = BASE._phase_weights


def _phase_weights(day, step, opponent, player_index):
    if player_index == 1 and day <= 17:
        if step == 0:
            BASE.USE_MELON_PRESSURE = None
            BASE.USE_P0_PURE_CROP_MIDDLE = None
        return {"MELON": 0.82, "CARROT": 0.08, "WHEAT": 0.10}
    return _original_phase_weights(day, step, opponent, player_index)


BASE._phase_weights = _phase_weights


def agent(obs):
    return BASE.agent(obs)

