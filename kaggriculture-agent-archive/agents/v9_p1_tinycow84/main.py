"""Local V9 experiment: keep V8, but avoid the low-melon branch for
seat-one opponents that show at least three cows and no more than one crop.

This wrapper is for counterfactual replay evaluation only.  A validated Kaggle
submission is flattened back to one dependency-free ``main.py``.
"""

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
SPEC = spec_from_file_location("kaggriculture_v8_tinycow84_base", BASE_PATH)
BASE = module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

_original_phase_weights = BASE._phase_weights
_force_tiny_cow_high_melon = None


def _phase_weights(day, step, opponent, player_index):
    global _force_tiny_cow_high_melon

    if step == 0:
        _force_tiny_cow_high_melon = None

    weights = _original_phase_weights(day, step, opponent, player_index)
    if player_index != 1 or day > 17:
        return weights

    if _force_tiny_cow_high_melon is None and day >= 1:
        crops = BASE._plant_counts(opponent)
        animals, _ = BASE._animal_counts(opponent)
        _force_tiny_cow_high_melon = (
            animals.get("COW", 0) >= 3 and sum(crops.values()) <= 1
        )

    if _force_tiny_cow_high_melon:
        return {"MELON": 0.84, "CARROT": 0.08, "WHEAT": 0.08}
    return weights


BASE._phase_weights = _phase_weights


def agent(obs):
    return BASE.agent(obs)

