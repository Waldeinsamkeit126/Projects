"""Build a state-aware replay-nearest-neighbor candidate from public games."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import tarfile
import zlib
from pathlib import Path


ITEMS = (
    "WHEAT",
    "MELON",
    "STRAWBERRY",
    "CARROT",
    "TOMATO",
    "MILK",
    "WOOL",
    "FERTILIZER",
    "EGG",
)
CROPS = ITEMS[:5]
ANIMALS = ("COW", "SHEEP", "GOOSE")
KINDS = ("PASTURE", "COOP", "WEED")


def position_count(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    if not value:
        return 0
    return len(str(value).split("  "))


def raw_signature(observation: dict[str, object], seat: int) -> list[int]:
    farm = (observation.get("farms") or [])[seat]
    counts = {name: 0 for name in (*CROPS, *ANIMALS, *KINDS)}
    uncared = unfed = 0
    for row in farm.get("tiles") or ():
        for tile in row or ():
            if not isinstance(tile, dict):
                continue
            for field in ("crop", "animal", "kind"):
                value = str(tile.get(field) or "")
                if value in counts:
                    counts[value] += 1
            if tile.get("animal"):
                unfed += int(not bool(tile.get("fed", True)))
                uncared += int(not bool(tile.get("cared_for", True)))
    private = observation.get("private") or {}
    shed = private.get("shed") or {}
    seeds = private.get("seeds") or {}
    prices = ((observation.get("market") or {}).get("prices") or {})
    quadrants = farm.get("unlocked_quadrants") or ()
    if isinstance(quadrants, str):
        quadrants = quadrants.split()
    return [
        int(farm.get("money") or 0),
        position_count(farm.get("hands")),
        len(quadrants),
        int(farm.get("hires_today") or 0),
        *(int(counts[name]) for name in CROPS),
        *(int(counts[name]) for name in ANIMALS),
        *(int(counts[name]) for name in KINDS),
        unfed,
        uncared,
        *(int(shed.get(name) or 0) for name in ITEMS),
        *(int(seeds.get(name) or 0) for name in CROPS),
        *(int(prices.get(name) or 0) for name in ITEMS),
    ]


def load_expert(path: Path, player_name: str) -> dict[str, object]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = [str(agent.get("Name", "")) for agent in replay["info"]["Agents"]]
    seat = names.index(player_name)
    actions: list[object] = []
    shops: list[list[str]] = []
    signatures: list[list[int]] = []
    step_count = len(replay["steps"])
    for runtime_step in range(step_count):
        state = replay["steps"][runtime_step][seat]
        observation = state.get("observation") or {}
        action_step = min(runtime_step + 1, step_count - 1)
        actions.append(replay["steps"][action_step][seat].get("action") or {})
        shops.append(list(((observation.get("town") or {}).get("unlocked_shops") or ())))
        signatures.append(raw_signature(observation, seat))
    return {
        "id": int(path.stem),
        "seat": seat,
        "reward": int(replay["rewards"][seat]),
        "actions": actions,
        "shops": shops,
        "signatures": signatures,
    }


RUNTIME = r'''

# --- E310 current-leader state-KNN imitation policy ---
_E310_EXPERTS = json.loads(zlib.decompress(base64.b85decode(__PAYLOAD__)).decode("utf-8"))
_E310_WEIGHTS = (
    0.01, 20.0, 50.0, 10.0,
    8.0, 8.0, 8.0, 8.0, 8.0,
    15.0, 15.0, 15.0,
    8.0, 8.0, 8.0,
    6.0, 4.0,
    3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0,
    3.0, 3.0, 3.0, 3.0, 3.0,
    0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
)
_E310_ITEMS = ("WHEAT", "MELON", "STRAWBERRY", "CARROT", "TOMATO", "MILK", "WOOL", "FERTILIZER", "EGG")
_E310_CROPS = _E310_ITEMS[:5]
_E310_ANIMALS = ("COW", "SHEEP", "GOOSE")
_E310_KINDS = ("PASTURE", "COOP", "WEED")
__version__ = "E310-current-leader-state-KNN-v1"


def _e310_position_count(value):
    if isinstance(value, list):
        return len(value)
    if not value:
        return 0
    return len(str(value).split("  "))


def _e310_signature(obs, seat):
    farm = (_get(obs, "farms", []) or [])[seat]
    counts = {name: 0 for name in (*_E310_CROPS, *_E310_ANIMALS, *_E310_KINDS)}
    uncared = 0
    unfed = 0
    for row in (_get(farm, "tiles", []) or []):
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            for field in ("crop", "animal", "kind"):
                value = str(tile.get(field) or "")
                if value in counts:
                    counts[value] += 1
            if tile.get("animal"):
                unfed += int(not bool(tile.get("fed", True)))
                uncared += int(not bool(tile.get("cared_for", True)))
    private = _get(obs, "private", {}) or {}
    shed = _get(private, "shed", {}) or {}
    seeds = _get(private, "seeds", {}) or {}
    prices = _get(_get(obs, "market", {}) or {}, "prices", {}) or {}
    quadrants = _get(farm, "unlocked_quadrants", []) or []
    if isinstance(quadrants, str):
        quadrants = quadrants.split()
    return (
        int(_get(farm, "money", 0) or 0),
        _e310_position_count(_get(farm, "hands", []) or []),
        len(quadrants),
        int(_get(farm, "hires_today", 0) or 0),
        *(int(counts[name]) for name in _E310_CROPS),
        *(int(counts[name]) for name in _E310_ANIMALS),
        *(int(counts[name]) for name in _E310_KINDS),
        unfed,
        uncared,
        *(int(shed.get(name, 0) or 0) for name in _E310_ITEMS),
        *(int(seeds.get(name, 0) or 0) for name in _E310_CROPS),
        *(int(prices.get(name, 0) or 0) for name in _E310_ITEMS),
    )


def _e310_shops(obs):
    return tuple(str(value) for value in (_get(_get(obs, "town", {}) or {}, "unlocked_shops", []) or []))


def _e310_common_prefix(left, right):
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def _e310_select(obs, step):
    seat = _seat(obs)
    shops = _e310_shops(obs)
    signature = _e310_signature(obs, seat)
    best = None
    best_key = None
    for expert in _E310_EXPERTS:
        if int(expert["seat"]) != seat:
            continue
        expert_step = min(step, len(expert["actions"]) - 1)
        matched = _e310_common_prefix(shops, tuple(expert["shops"][expert_step]))
        state_distance = sum(
            abs(float(a) - float(b)) * weight
            for a, b, weight in zip(signature, expert["signatures"][expert_step], _E310_WEIGHTS)
        )
        key = (matched, -state_distance, int(expert["reward"]))
        if best_key is None or key > best_key:
            best = expert
            best_key = key
    return best


_E310_BASE_AGENT = agent


def agent(obs, configuration=None):
    del configuration
    global _ACTIONS
    try:
        step = min(max(0, int(_get(obs, "step", 0) or 0)), 719)
        expert = _e310_select(obs, step)
        if expert is None:
            return _E310_BASE_AGENT(obs)
        route = expert["actions"]
        _ACTIONS = route
        action = _weed_repair_action(obs, _copy_action(route[min(step, len(route) - 1)]), step)
        action = _v17_feed_guard(obs, action, step)
        action = _v17_room_evac(obs, action, step)
        action = _repay_shift(obs, action, step)
        action = _rank_sell_slots(obs, action, None)
        action = _preempt_shift(obs, action, step)
        action = _v17_r5_counter(obs, action, step)
        action = _v17_md_counter(obs, action, step)
        action = _v17_room_guard(obs, action, step)
        action = _terminal_liquidation(obs, action, step)
        return _align_hands(action, obs)
    except Exception:
        return _E310_BASE_AGENT(obs)
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_directory", type=Path)
    parser.add_argument("base_agent", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--player", default="カワシギ")
    args = parser.parse_args()

    experts = [load_expert(path, args.player) for path in sorted(args.episode_directory.glob("*.json"))]
    encoded = base64.b85encode(
        zlib.compress(json.dumps(experts, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    ).decode("ascii")
    base = args.base_agent.read_text(encoding="utf-8")
    suffix = RUNTIME.replace("__PAYLOAD__", repr(encoded))
    source = (base.rstrip() + "\n" + suffix.lstrip()).encode("utf-8")
    compile(source, "main.py", "exec")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    main_path = args.output_directory / "main.py"
    main_path.write_bytes(source)
    archive_path = args.output_directory / "submission.tar.gz"
    with tarfile.open(archive_path, "w:gz", compresslevel=9) as archive:
        archive.add(main_path, arcname="main.py")
    report = {
        "experts": len(experts),
        "seat0": sum(int(item["seat"]) == 0 for item in experts),
        "seat1": sum(int(item["seat"]) == 1 for item in experts),
        "main_path": str(main_path.resolve()),
        "main_bytes": len(source),
        "main_sha256": hashlib.sha256(source).hexdigest(),
        "archive_path": str(archive_path.resolve()),
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    }
    (args.output_directory / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
