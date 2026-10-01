"""Generate conservative one-change-at-a-time Indar ablation agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VARIANTS = {
    "r5_off": '''
_E320_ORIGINAL_R5_COUNTER = _v17_r5_counter
def _v17_r5_counter(obs, action, step):
    return action
__version__ = "E320-indar-r5-off"
''',
    "md_off": '''
_V17_MD_FRACTION = 0.0
__version__ = "E321-indar-md-off"
''',
    "both_counters_off": '''
_E322_ORIGINAL_R5_COUNTER = _v17_r5_counter
def _v17_r5_counter(obs, action, step):
    return action
_V17_MD_FRACTION = 0.0
__version__ = "E322-indar-counters-off"
''',
    "room_guard_off": '''
_V17_ROOM_GUARD = False
__version__ = "E323-indar-room-guard-off"
''',
    "preempt_wool_exact": '''
_PREEMPT_ENABLED = True
_PREEMPT_FRACTION = 1.0
_PREEMPT_MAX_BATCH = 20
_PREEMPT_MAX_CLONE_DISTANCE = 0
_PREEMPT_MIN_PRICE_RATIO = 0.75
_PREEMPT_MIN_FUTURE_QUANTITY = 4
_PREEMPT_START = 300
_PREEMPT_STOP = 620
_PREMIUM = ("WOOL",)
__version__ = "E324-indar-preempt-wool-exact"
''',
    "preempt_milk_wool_exact": '''
_PREEMPT_ENABLED = True
_PREEMPT_FRACTION = 1.0
_PREEMPT_MAX_BATCH = 20
_PREEMPT_MAX_CLONE_DISTANCE = 0
_PREEMPT_MIN_PRICE_RATIO = 0.75
_PREEMPT_MIN_FUTURE_QUANTITY = 4
_PREEMPT_START = 300
_PREEMPT_STOP = 620
_PREMIUM = ("MILK", "WOOL")
__version__ = "E325-indar-preempt-milk-wool-exact"
''',
    "preempt_wool_near": '''
_PREEMPT_ENABLED = True
_PREEMPT_FRACTION = 1.0
_PREEMPT_MAX_BATCH = 16
_PREEMPT_MAX_CLONE_DISTANCE = 2
_PREEMPT_MIN_PRICE_RATIO = 0.9
_PREEMPT_MIN_FUTURE_QUANTITY = 5
_PREEMPT_START = 340
_PREEMPT_STOP = 600
_PREMIUM = ("WOOL",)
__version__ = "E326-indar-preempt-wool-near"
''',
    "preempt_wool_near_seat0": '''
_PREEMPT_FRACTION = 1.0
_PREEMPT_MAX_BATCH = 16
_PREEMPT_MAX_CLONE_DISTANCE = 2
_PREEMPT_MIN_PRICE_RATIO = 0.9
_PREEMPT_MIN_FUTURE_QUANTITY = 5
_PREEMPT_START = 340
_PREEMPT_STOP = 600
_PREMIUM = ("WOOL",)
_E328_BASE_AGENT = agent

def agent(obs, configuration=None):
    global _PREEMPT_ENABLED
    _PREEMPT_ENABLED = _seat(obs) == 0
    return _E328_BASE_AGENT(obs)

__version__ = "E328-indar-preempt-wool-near-seat0"
''',
    "yarn_no_dominance": '''
_E327_ORIGINAL_SELECTOR = _e279_selected_expert
def _e279_selected_expert(obs):
    seat = _seat(obs)
    step = _e279_step(obs)
    state = _E279_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {"last_step": step, "shops": (), "expert": None}
        _E279_STATE[seat] = state
    state["last_step"] = step
    if step <= _E279_DECISION_STEP:
        state["shops"] = _e279_shops(obs)
    if state.get("expert") is None and step >= _E279_DECISION_STEP:
        state["expert"] = "high" if "YARN_STORE" in tuple(state.get("shops") or ()) else "low"
    return str(state.get("expert") or "low")
__version__ = "E327-indar-yarn-no-dominance"
''',
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_agent", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    base = args.base_agent.read_text(encoding="utf-8").rstrip() + "\n"
    report: dict[str, str] = {}
    for name, suffix in VARIANTS.items():
        directory = args.output_directory / name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "main.py"
        source = base + "\n" + suffix.strip() + "\n"
        compile(source, str(path), "exec")
        path.write_text(source, encoding="utf-8")
        report[name] = str(path.resolve())
    (args.output_directory / "manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
