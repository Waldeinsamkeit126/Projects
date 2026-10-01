"""Closed-loop V12 experiment: V10 for seat zero, V6 for seat one.

The two seats have materially different market timing.  This local wrapper
keeps each previously validated policy intact so the seat split can be tested
before flattening the shared implementation into a submission artifact.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def _load(name, relative_path):
    path = ROOT / relative_path
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load policy: {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEAT_ZERO = _load(
    "kaggriculture_v12_seat_zero",
    Path("outputs/kaggriculture_agent/v10_straw4x50_35/main.py"),
)
SEAT_ONE = _load(
    "kaggriculture_v12_seat_one",
    Path("outputs/kaggriculture_agent/v6_player1_selective/main.py"),
)


def _player_index(obs):
    if isinstance(obs, dict):
        return int(obs.get("player", 0))
    return int(getattr(obs, "player", 0))


def agent(obs):
    if _player_index(obs) == 0:
        return SEAT_ZERO.agent(obs)
    return SEAT_ONE.agent(obs)
