"""Benchmark wrapper that forces Indar E279's low-capacity route."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_BASE_PATH = (
    Path(__file__).resolve().parents[4]
    / "outputs"
    / "kaggriculture_agent"
    / "public_indar_market_v1"
    / "main.py"
)
_SPEC = importlib.util.spec_from_file_location("indar_force_low_base", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Cannot load Indar base agent: {_BASE_PATH}")
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)


def agent(obs, configuration=None):
    del configuration
    _BASE._ACTIONS = _BASE._E279_LOW_ACTIONS
    return _BASE._E279_PUBLIC_AGENT(obs)
