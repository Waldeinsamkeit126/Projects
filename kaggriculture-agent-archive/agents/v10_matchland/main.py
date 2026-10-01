"""Kaggriculture competition agent.

The agent is deliberately dependency-free so this file can be submitted directly
to Kaggle.  It combines five ideas:

* cheap daily farm hands for parallel work;
* deterministic task assignment and shortest-path routing;
* a crop-and-livestock portfolio with daily feed/care/collection rounds;
* market-health-aware herd growth and opponent-aware production choices;
* paced selling for products whose market price collapses under a glut.

The public entry point required by the competition is ``agent(obs)``.
"""

from collections import deque
import math


CROPS = {
    "WHEAT": {
        "seed": 10,
        "first": 2,
        "max_day": 4,
        "max_yield": 6,
        "ongoing": False,
    },
    "CARROT": {
        "seed": 20,
        "first": 2,
        "max_day": 3,
        "max_yield": 4,
        "ongoing": False,
    },
    "TOMATO": {
        "seed": 50,
        "first": 8,
        "max_day": 11,
        "max_yield": 4,
        "ongoing": True,
    },
    "STRAWBERRY": {
        "seed": 100,
        "first": 10,
        "max_day": 16,
        "max_yield": 4,
        "ongoing": True,
    },
    "MELON": {
        "seed": 80,
        "first": 10,
        # With daily watering, its six-unit cap is reached on age 10.
        "max_day": 10,
        "max_yield": 6,
        "ongoing": False,
    },
}

ANIMALS = {
    "GOOSE": {
        "cost": 300,
        "structure": "COOP",
        "product": "EGG",
        "first": 4,
        "interval": 1,
        "max_held": 4,
    },
    "COW": {
        "cost": 400,
        "structure": "PASTURE",
        "product": "MILK",
        "first": 8,
        "interval": 2,
        "max_held": 6,
    },
    "SHEEP": {
        "cost": 500,
        "structure": "PASTURE",
        "product": "WOOL",
        "first": 6,
        "interval": 3,
        "max_held": 6,
    },
}

BASE_PRICE = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}

PRODUCTS = tuple(BASE_PRICE)

# Maximum quantity deliberately sold by one order before the final liquidation.
# Wheat/egg prices are glut-resistant; premium products are released gradually.
SELL_CAP = {
    "WHEAT": 100,
    "CARROT": 24,
    "TOMATO": 12,
    "STRAWBERRY": 3,
    "MELON": 24,
    "EGG": 18,
    "MILK": 8,
    "WOOL": 6,
    "FERTILIZER": 8,
}

CROWD_RISK = {
    "MELON": 0.15,
    "STRAWBERRY": 2.4,
    "TOMATO": 1.1,
    "CARROT": 0.55,
    "WHEAT": 0.20,
}

ANIMAL_SHARE = 0.35
ANIMAL_START = 5.0
ANIMAL_RAMP_PER_DAY = 0.75
ANIMAL_STOP_HEALTH = 0.50
ANIMAL_SLOW_HEALTH = 0.75
ANIMAL_BASE_WEIGHTS = {"GOOSE": 0.08, "COW": 0.55, "SHEEP": 0.37}
ANIMAL_CROWD_PENALTY = 0.06

# Counterfactual replay tests showed that forcing the third quadrant early
# over-invests in seeds and labor.  Keep the proven V2 rule: expand only after
# the currently unlocked area is genuinely saturated and retain a cash buffer.
LAND_MAX_QUADRANTS = 4
LAND_START_DAY = {1: 5, 2: 5, 3: 5}
LAND_FORCE_DAY = {1: 99, 2: 99, 3: 99}
LAND_OCCUPANCY = {1: 0.80, 2: 0.80, 3: 0.80}
LAND_CASH_RESERVE = {1: 1200, 2: 1200, 3: 1200}

# Pick one early crop regime after the opponent's day-zero portfolio is fully
# visible. Reset this per episode so concurrent local evaluations remain
# deterministic.
USE_MELON_PRESSURE = None
USE_P0_PURE_CROP_MIDDLE = None
USE_P1_TINY_COW_MIDDLE = None

DIRECTIONS = (
    ("WEST", -1, 0),
    ("NORTH", 0, -1),
    ("EAST", 1, 0),
    ("SOUTH", 0, 1),
)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_dict(value):
    return value if isinstance(value, dict) else (value or {})


def _quadrant(x, y, size):
    half = size // 2
    return ("N" if y < half else "S") + ("W" if x < half else "E")


def _shed_tiles(size):
    half = size // 2
    return (
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    )


def _unlocked_cells(farm):
    tiles = farm["tiles"]
    return [
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile != "LOCKED"
    ]


def _plant_counts(farm):
    counts = {crop: 0 for crop in CROPS}
    for row in farm["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                crop = tile.get("crop")
                if crop in counts:
                    counts[crop] += 1
    return counts


def _animal_counts(farm):
    counts = {animal: 0 for animal in ANIMALS}
    empty_structures = {"COOP": 0, "PASTURE": 0}
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            animal = tile.get("animal")
            if animal in counts:
                counts[animal] += 1
            elif tile.get("kind") in empty_structures:
                empty_structures[tile["kind"]] += 1
    return counts, empty_structures


def _inventory_totals(private):
    totals = {}
    for item, value in _as_dict(private.get("shed", {})).items():
        totals[item] = totals.get(item, 0) + max(0, int(value))
    for inv in private.get("inventories", []) or []:
        for item, value in _as_dict(inv).items():
            totals[item] = totals.get(item, 0) + max(0, int(value))
    return totals


def _phase_weights(day, step, opponent, player_index):
    global USE_MELON_PRESSURE, USE_P0_PURE_CROP_MIDDLE, USE_P1_TINY_COW_MIDDLE

    if step == 0:
        USE_MELON_PRESSURE = None
        USE_P0_PURE_CROP_MIDDLE = None
        USE_P1_TINY_COW_MIDDLE = None

    # Leave enough time on days 28-29 to turn inventory into banked coins.
    if day <= 17:
        if USE_MELON_PRESSURE is None and day >= 1:
            opp_crops = _plant_counts(opponent)
            opp_animals, _ = _animal_counts(opponent)
            animal_total = sum(opp_animals.values())
            mixed_animal_opening = animal_total >= 4 and opp_crops.get("CARROT", 0) > 0
            compact_melon_opening = (
                animal_total == 4
                and opp_crops.get("MELON", 0) == 9
                and opp_crops.get("CARROT", 0) == 0
                and opp_crops.get("WHEAT", 0) == 0
            )
            crop_total = sum(opp_crops.values())
            cow_total = opp_animals.get("COW", 0)
            crowded_cow_opening = (
                (cow_total >= 3 and 1 <= crop_total <= 17)
                or (
                    cow_total >= 2
                    and 6 <= crop_total <= 17
                    and opp_crops.get("CARROT", 0) != 1
                )
            )
            extreme_field_opening = animal_total == 0 and crop_total >= 40
            if player_index == 0:
                USE_P0_PURE_CROP_MIDDLE = animal_total == 0
                USE_MELON_PRESSURE = (
                    mixed_animal_opening or compact_melon_opening
                )
            else:
                USE_P1_TINY_COW_MIDDLE = cow_total >= 3 and crop_total <= 1
                USE_MELON_PRESSURE = not (
                    crowded_cow_opening or extreme_field_opening
                )
        # Keep a middle crop mix after a pure-crop opponent is visible. This
        # preserves the V6 day-zero probe while avoiding its weak 78/8/14
        # follow-up against the current pure-crop meta.
        if USE_P0_PURE_CROP_MIDDLE:
            return {
                "MELON": 0.81,
                "CARROT": 0.08,
                "WHEAT": 0.11,
            }
        # Against the tiny three-cow opening, the old 78/8/14 mix left too
        # much income on the table in both observed seat-one seeds.  A narrow
        # 80/8/12 middle mix improves margin without changing any other branch.
        if player_index == 1 and USE_P1_TINY_COW_MIDDLE:
            return {
                "MELON": 0.80,
                "CARROT": 0.08,
                "WHEAT": 0.12,
            }
        # Player zero moves first in the market on day zero. Probe with the
        # higher-melon regime for that opening day, then keep it only for the
        # opponent portfolios that benefited from sustained pressure.
        if USE_MELON_PRESSURE or USE_MELON_PRESSURE is None:
            return {
                "MELON": 0.84,
                "CARROT": 0.08,
                "WHEAT": 0.08,
            }
        return {
            "MELON": 0.78,
            "CARROT": 0.08,
            "WHEAT": 0.14,
        }
    if day <= 26:
        return {"CARROT": 0.55, "WHEAT": 0.45}
    return {}


def _target_counts(obs, farm, opponent, cell_count):
    """Allocate a portfolio while reacting to prices and visible opponent crops."""
    weights = _phase_weights(
        int(_get(obs, "day", 0)),
        int(_get(obs, "step", 0)),
        opponent,
        int(_get(obs, "player", 0)),
    )
    if not weights or cell_count <= 0:
        return {crop: 0 for crop in CROPS}

    prices = _as_dict(_as_dict(_get(obs, "market", {})).get("prices", {}))
    opp_counts = _plant_counts(opponent)
    opp_cells = max(1, len(_unlocked_cells(opponent)))
    adjusted = {}
    for crop, weight in weights.items():
        price_ratio = float(prices.get(crop, BASE_PRICE[crop])) / BASE_PRICE[crop]
        price_factor = min(1.45, max(0.28, price_ratio))
        opp_share = opp_counts[crop] / opp_cells
        crowd_factor = 1.0 / (1.0 + CROWD_RISK[crop] * opp_share)
        adjusted[crop] = weight * price_factor * crowd_factor

    total = sum(adjusted.values()) or 1.0
    raw = {crop: cell_count * value / total for crop, value in adjusted.items()}
    targets = {crop: int(math.floor(raw.get(crop, 0.0))) for crop in CROPS}
    remainder = cell_count - sum(targets.values())
    order = sorted(
        adjusted,
        key=lambda crop: (raw[crop] - math.floor(raw[crop]), adjusted[crop], crop),
        reverse=True,
    )
    for crop in order[:remainder]:
        targets[crop] += 1
    return targets


def _desired_animal_counts(obs, farm, opponent):
    """Ramp into a diversified herd while keeping room for high-ROI crops."""
    day = int(_get(obs, "day", 0))
    current, _ = _animal_counts(farm)
    current_total = sum(current.values())
    if day >= 25:
        return current

    capacity = max(current_total, int(len(_unlocked_cells(farm)) * ANIMAL_SHARE))
    prices = _as_dict(_as_dict(_get(obs, "market", {})).get("prices", {}))
    health = sum(
        float(prices.get(product, BASE_PRICE[product])) / BASE_PRICE[product]
        for product in ("EGG", "MILK", "WOOL")
    ) / 3.0
    ramp = int(ANIMAL_START + ANIMAL_RAMP_PER_DAY * day)
    if day >= 8 and health < ANIMAL_STOP_HEALTH:
        ramp = min(ramp, current_total + 1)
    elif day >= 8 and health < ANIMAL_SLOW_HEALTH:
        ramp = min(ramp, int(len(_unlocked_cells(farm)) * 0.45))
    target_total = max(current_total, min(capacity, ramp))
    opp_counts, _ = _animal_counts(opponent)
    base_weights = ANIMAL_BASE_WEIGHTS
    # Seat one reacts after the first mover has already influenced the market.
    # Penalize overlap slightly more strongly there while preserving V7's seat-zero
    # behavior exactly.
    crowd_penalty = (
        0.07 if int(_get(obs, "player", 0)) == 1 else ANIMAL_CROWD_PENALTY
    )
    scores = {}
    for animal, weight in base_weights.items():
        product = ANIMALS[animal]["product"]
        price_ratio = float(prices.get(product, BASE_PRICE[product])) / BASE_PRICE[product]
        crowd = 1.0 / (
            1.0 + crowd_penalty * opp_counts.get(animal, 0)
        )
        scores[animal] = weight * min(1.65, max(0.12, price_ratio)) * crowd

    desired = dict(current)
    for _ in range(max(0, target_total - current_total)):
        chosen = max(
            ANIMALS,
            key=lambda animal: (
                scores[animal] / (1.0 + 0.28 * desired[animal]),
                -ANIMALS[animal]["cost"],
                animal,
            ),
        )
        desired[chosen] += 1
    return desired


def _animal_build_plan(obs, farm, opponent):
    desired = _desired_animal_counts(obs, farm, opponent)
    current, empty_structures = _animal_counts(farm)
    existing_coops = current["GOOSE"] + empty_structures["COOP"]
    existing_pastures = current["COW"] + current["SHEEP"] + empty_structures["PASTURE"]
    need_coops = max(0, desired["GOOSE"] - existing_coops)
    need_pastures = max(
        0,
        desired["COW"] + desired["SHEEP"] - existing_pastures,
    )

    size = len(farm["tiles"])
    half = size // 2
    empties = [
        (x, y)
        for x, y in _unlocked_cells(farm)
        if farm["tiles"][y][x] is None
    ]
    empties.sort(
        key=lambda xy: (
            abs(xy[0] - (half - 0.5)) + abs(xy[1] - (half - 0.5)),
            (xy[0] * 17 + xy[1] * 31) % 101,
            xy[1],
            xy[0],
        )
    )
    plan = {}
    for xy in empties:
        if need_coops <= 0 and need_pastures <= 0:
            break
        if need_coops >= need_pastures and need_coops > 0:
            plan[xy] = "COOP"
            need_coops -= 1
        else:
            plan[xy] = "PASTURE"
            need_pastures -= 1
    return plan, desired


def _crop_plan(obs, farm, opponent):
    """Return empty-cell -> desired-crop and aggregate seed requirements."""
    build_plan, desired_animals = _animal_build_plan(obs, farm, opponent)
    animal_capacity = sum(desired_animals.values())
    cells = _unlocked_cells(farm)
    crop_capacity = max(0, len(cells) - animal_capacity)
    targets = _target_counts(obs, farm, opponent, crop_capacity)
    current = _plant_counts(farm)
    remaining = {
        crop: max(0, targets.get(crop, 0) - current.get(crop, 0))
        for crop in CROPS
    }

    empties = [
        xy
        for xy in cells
        if farm["tiles"][xy[1]][xy[0]] is None and xy not in build_plan
    ]
    empties.sort(key=lambda xy: ((xy[0] * 17 + xy[1] * 31) % 101, xy[1], xy[0]))

    plan = {}
    for xy in empties:
        available = [crop for crop, count in remaining.items() if count > 0]
        if not available:
            break
        crop = max(
            available,
            key=lambda name: (
                remaining[name] / max(1, targets.get(name, 0)),
                CROPS[name]["max_yield"] * BASE_PRICE[name] - CROPS[name]["seed"],
                name,
            ),
        )
        plan[xy] = crop
        remaining[crop] -= 1

    need = {crop: 0 for crop in CROPS}
    for crop in plan.values():
        need[crop] += 1
    return plan, need


def _ready_to_harvest(tile, day):
    crop = tile.get("crop")
    if crop not in CROPS or tile.get("yield_units", 0) <= 0:
        return False
    data = CROPS[crop]
    age = day - int(tile.get("planted_day", day))
    if day >= 28:
        return age >= data["first"]
    if data["ongoing"]:
        return tile.get("yield_units", 0) >= 2
    return age >= data["max_day"] or tile.get("yield_units", 0) >= data["max_yield"]


def _build_tasks(obs, farm, opponent, private):
    day = int(_get(obs, "day", 0))
    hour = int(_get(obs, "hour", 0))
    seeds = dict(_as_dict(private.get("seeds", {})))
    crop_plan, _ = _crop_plan(obs, farm, opponent)
    animal_build_plan, desired_animals = _animal_build_plan(obs, farm, opponent)
    animal_current, _ = _animal_counts(farm)
    inventory_totals = _inventory_totals(private)
    placement_allowance = {
        animal: min(
            max(0, desired_animals[animal] - animal_current[animal]),
            max(0, int(inventory_totals.get(animal, 0))),
        )
        for animal in ANIMALS
    }

    # Atomic PLANT validation means we must never request more plants of a crop
    # in one turn than the currently available seed count.
    plant_allowance = {crop: max(0, int(seeds.get(crop, 0))) for crop in CROPS}
    tasks = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            xy = (x, y)
            if tile is None:
                structure = animal_build_plan.get(xy)
                if structure:
                    tasks.append(
                        (
                            3,
                            xy,
                            ["BUILD_COOP" if structure == "COOP" else "BUILD_PASTURE"],
                            None,
                        )
                    )
                    continue
                crop = crop_plan.get(xy)
                if hour <= 18 and crop and plant_allowance[crop] > 0:
                    tasks.append((5, xy, ["PLANT", crop], None))
                    plant_allowance[crop] -= 1
                continue
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "WEED":
                tasks.append((4, xy, ["DIG"], None))
                continue
            animal = tile.get("animal")
            if animal in ANIMALS:
                if not tile.get("fed_today", False):
                    urgent = 0 if tile.get("consecutive_unfed", 0) >= 1 else 1
                    tasks.append((urgent, xy, ["FEED"], "WHEAT"))
                if tile.get("yield_units", 0) > 0:
                    tasks.append((1, xy, ["HARVEST"], None))
                if not tile.get("cared_today", False):
                    tasks.append((2, xy, ["CARE"], None))
                if tile.get("fertilizer_available", False):
                    tasks.append((3, xy, ["COLLECT_FERTILIZER"], None))
                continue
            if tile.get("kind") in ("COOP", "PASTURE"):
                if tile.get("kind") == "COOP":
                    candidates = ["GOOSE"]
                else:
                    candidates = ["COW", "SHEEP"]
                candidates = [
                    candidate
                    for candidate in candidates
                    if placement_allowance.get(candidate, 0) > 0
                ]
                if candidates:
                    chosen = max(
                        candidates,
                        key=lambda candidate: (
                            desired_animals[candidate] - animal_current[candidate],
                            placement_allowance[candidate],
                            candidate,
                        ),
                    )
                    tasks.append((0, xy, ["PLACE", chosen], chosen))
                    placement_allowance[chosen] -= 1
                continue
            if tile.get("kind") != "PLANT":
                continue

            # On the liquidation days, realized inventory beats future yield.
            if day >= 28 and _ready_to_harvest(tile, day):
                tasks.append((0, xy, ["HARVEST"], None))
            elif not tile.get("watered_today", False):
                urgent = 0 if tile.get("consecutive_unwatered", 0) >= 1 else 1
                tasks.append((urgent, xy, ["WATER"], None))
            elif _ready_to_harvest(tile, day):
                tasks.append((2, xy, ["HARVEST"], None))
    return tasks


def _passable(farm, x, y):
    size = len(farm["tiles"])
    return 0 <= x < size and 0 <= y < size and farm["tiles"][y][x] != "LOCKED"


def _next_move(farm, start, goals, worker_index=0):
    """Return the first action on a shortest path to any goal."""
    start = tuple(start)
    goals = set(tuple(goal) for goal in goals)
    if start in goals:
        return ["PASS"]

    # Rotate equal-length route preference across workers to reduce clumping.
    shift = worker_index % len(DIRECTIONS)
    directions = DIRECTIONS[shift:] + DIRECTIONS[:shift]
    queue = deque([(start, None)])
    seen = {start}
    while queue:
        (x, y), first = queue.popleft()
        for name, dx, dy in directions:
            nx, ny = x + dx, y + dy
            nxt = (nx, ny)
            if nxt in seen or not _passable(farm, nx, ny):
                continue
            first_action = first or name
            if nxt in goals:
                return [first_action]
            seen.add(nxt)
            queue.append((nxt, first_action))
    return ["PASS"]


def _inventory_has_sale(inv):
    return any(int(inv.get(item, 0)) > 0 for item in PRODUCTS if item != "WHEAT")


def _worker_actions(obs, farm, opponent, private):
    tasks = _build_tasks(obs, farm, opponent, private)
    positions = [farm["farmer"]] + list(farm.get("hands", []))
    inventories = list(private.get("inventories", []))
    while len(inventories) < len(positions):
        inventories.append({})

    size = len(farm["tiles"])
    shed_goals = [xy for xy in _shed_tiles(size) if _passable(farm, xy[0], xy[1])]
    day = int(_get(obs, "day", 0))
    hour = int(_get(obs, "hour", 0))
    actions = [["PASS"] for _ in positions]
    shed_goal_set = set(shed_goals)
    unassigned = set(range(len(positions)))

    # On the final day every harvested unit must reach the shed before it can
    # be sold. Earlier inventories auto-drop at end of day, so returning them
    # manually would waste a large share of the workforce.
    if day >= 29:
        for idx, (pos, inv) in enumerate(zip(positions, inventories)):
            if not _inventory_has_sale(_as_dict(inv)):
                continue
            if tuple(pos) in shed_goal_set:
                actions[idx] = ["DROP"]
            else:
                actions[idx] = _next_move(farm, pos, shed_goals, idx)
            unassigned.discard(idx)

    available = list(tasks)
    shed_stock = dict(_as_dict(private.get("shed", {})))

    # Workers spawn at the shed every morning. Load animals waiting for an
    # empty structure first, then distribute a small wheat ration among the
    # remaining workers for daily feeding rounds.
    placement_need = {animal: 0 for animal in ANIMALS}
    for _, _, action, required in available:
        if action and action[0] == "PLACE" and required in placement_need:
            placement_need[required] += 1
    for inv in inventories:
        for animal in ANIMALS:
            placement_need[animal] = max(
                0,
                placement_need[animal] - int(_as_dict(inv).get(animal, 0)),
            )

    feed_need = sum(1 for _, _, action, _ in available if action and action[0] == "FEED")
    carried_wheat = sum(int(_as_dict(inv).get("WHEAT", 0)) for inv in inventories)
    wheat_to_load = max(0, feed_need - carried_wheat)
    for idx in sorted(list(unassigned)):
        pos = tuple(positions[idx])
        inv = _as_dict(inventories[idx])
        if pos not in shed_goal_set or inv:
            continue
        pickup_animal = None
        for animal in sorted(
            ANIMALS,
            key=lambda name: (placement_need[name], shed_stock.get(name, 0), name),
            reverse=True,
        ):
            if placement_need[animal] > 0 and int(shed_stock.get(animal, 0)) > 0:
                pickup_animal = animal
                break
        if pickup_animal:
            actions[idx] = ["PICKUP", pickup_animal, 1]
            placement_need[pickup_animal] -= 1
            shed_stock[pickup_animal] = int(shed_stock.get(pickup_animal, 0)) - 1
            unassigned.remove(idx)
            continue
        wheat_available = max(0, int(shed_stock.get("WHEAT", 0)))
        if wheat_to_load > 0 and wheat_available > 0:
            qty = min(6, wheat_to_load, wheat_available)
            actions[idx] = ["PICKUP", "WHEAT", qty]
            wheat_to_load -= qty
            shed_stock["WHEAT"] = wheat_available - qty
            unassigned.remove(idx)

    # Global greedy matching is markedly better than letting every hand chase
    # the same nearest plant.  Task priority dominates travel distance.
    while unassigned and available:
        best = None
        for idx in unassigned:
            px, py = positions[idx]
            inv = _as_dict(inventories[idx])
            for task_index, (priority, (tx, ty), action, required) in enumerate(available):
                if required and int(inv.get(required, 0)) <= 0:
                    continue
                key = (priority, abs(px - tx) + abs(py - ty), idx, ty, tx)
                if best is None or key < best[0]:
                    best = (key, idx, task_index, (tx, ty), action)
        if best is None:
            break
        _, idx, task_index, target, task_action = best
        pos = tuple(positions[idx])
        actions[idx] = task_action if pos == target else _next_move(farm, pos, [target], idx)
        unassigned.remove(idx)
        available.pop(task_index)

    # If required supplies still exist at the shed, idle workers stage there
    # for pickup on the next turn instead of standing in a remote corner.
    supply_waiting = any(placement_need.values()) or wheat_to_load > 0
    if supply_waiting:
        for idx in sorted(unassigned):
            if tuple(positions[idx]) not in shed_goal_set:
                actions[idx] = _next_move(farm, positions[idx], shed_goals, idx)

    return actions[0], actions[1:]


def _fib_hire_cost(index):
    a, b = 1, 1
    for _ in range(index):
        a, b = b, a + b
    return a


def _desired_hands(farm, day):
    cells = _unlocked_cells(farm)
    plants = sum(
        1
        for x, y in cells
        if isinstance(farm["tiles"][y][x], dict)
        and farm["tiles"][y][x].get("kind") == "PLANT"
    )
    animal_counts, empty_structures = _animal_counts(farm)
    animals = sum(animal_counts.values())
    structures = sum(empty_structures.values())
    workload = plants + animals * 3.2 + structures * 1.5
    if workload <= 30:
        desired = 10
    elif workload <= 65:
        desired = 12
    elif workload <= 100:
        desired = 13
    else:
        desired = 14
    if day >= 29:
        desired = min(desired, 12)
    return desired


def _sell_orders(obs, private):
    shed = _as_dict(private.get("shed", {}))
    prices = _as_dict(_as_dict(_get(obs, "market", {})).get("prices", {}))
    day = int(_get(obs, "day", 0))
    total = sum(max(0, int(value)) for value in shed.values())
    orders = []
    for item in PRODUCTS:
        held = max(0, int(shed.get(item, 0)))
        if held <= 0:
            continue
        if item == "WHEAT" and day < 29:
            continue
        price = float(prices.get(item, BASE_PRICE[item]))
        if day >= 28:
            qty = held
        elif price <= max(2, BASE_PRICE[item] * 0.12) and total < 85:
            continue
        elif total >= 85:
            qty = min(held, max(SELL_CAP[item], 12))
        else:
            qty = min(held, SELL_CAP[item])
        if qty > 0:
            value = qty * price
            orders.append((value, ["SELL", item, qty]))
    orders.sort(key=lambda pair: pair[0], reverse=True)
    return [order for _, order in orders]


def _seed_orders(obs, farm, opponent, private, budget):
    _, need = _crop_plan(obs, farm, opponent)
    seeds = _as_dict(private.get("seeds", {}))
    prices = _as_dict(_as_dict(_get(obs, "market", {})).get("prices", {}))
    candidates = []
    for crop, count in need.items():
        deficit = max(0, int(count) - int(seeds.get(crop, 0)))
        if deficit <= 0:
            continue
        expected = CROPS[crop]["max_yield"] * float(prices.get(crop, BASE_PRICE[crop]))
        score = (expected - CROPS[crop]["seed"]) / max(1, CROPS[crop]["max_day"])
        candidates.append((score, crop, deficit))
    candidates.sort(reverse=True)

    orders = []
    reserve = 250
    total_bought = 0
    for _, crop, deficit in candidates:
        affordable = max(0, int((budget - reserve) // CROPS[crop]["seed"]))
        qty = min(deficit, affordable, 4, max(0, 8 - total_bought))
        if qty <= 0:
            continue
        orders.append(["BUY_SEED", crop, qty])
        budget -= qty * CROPS[crop]["seed"]
        total_bought += qty
        if total_bought >= 8:
            break
    return orders


def _feed_order(obs, farm, private, budget):
    if int(_get(obs, "day", 0)) >= 29:
        return None, budget
    animal_counts, _ = _animal_counts(farm)
    desired = _desired_animal_counts(obs, farm, farm)
    pending = sum(
        int(_inventory_totals(private).get(animal, 0))
        for animal in ANIMALS
    )
    animals = max(
        sum(animal_counts.values()) + pending,
        sum(desired.values()),
    )
    if animals <= 0:
        return None, budget
    totals = _inventory_totals(private)
    stock = max(0, int(totals.get("WHEAT", 0)))
    target = max(8, animals * 2)
    needed = max(0, target - stock)
    if needed <= 0:
        return None, budget
    prices = _as_dict(_as_dict(_get(obs, "market", {})).get("prices", {}))
    unit_price = max(1.0, float(prices.get("WHEAT", BASE_PRICE["WHEAT"])))
    affordable = max(0, int((budget - 250) // unit_price))
    qty = min(needed, affordable, 40)
    if qty <= 0:
        return None, budget
    return ["BUY_PRODUCT", "WHEAT", qty], budget - qty * unit_price


def _animal_orders(obs, farm, opponent, private, budget):
    desired = _desired_animal_counts(obs, farm, opponent)
    current, _ = _animal_counts(farm)
    totals = _inventory_totals(private)
    prices = _as_dict(_as_dict(_get(obs, "market", {})).get("prices", {}))
    candidates = []
    for animal, data in ANIMALS.items():
        deficit = max(
            0,
            desired[animal] - current[animal] - int(totals.get(animal, 0)),
        )
        if deficit <= 0:
            continue
        product_price = float(prices.get(data["product"], BASE_PRICE[data["product"]]))
        daily_units = {"GOOSE": 2.0, "COW": 1.5, "SHEEP": 4.0 / 3.0}[animal]
        payback_score = (daily_units * product_price + 35.0) / data["cost"]
        candidates.append((payback_score, animal, deficit))
    candidates.sort(reverse=True)

    orders = []
    for _, animal, deficit in candidates:
        cost = ANIMALS[animal]["cost"]
        affordable = max(0, int((budget - 300) // cost))
        qty = min(deficit, affordable, 5)
        if qty <= 0:
            continue
        orders.append(["BUY_ANIMAL", animal, qty])
        budget -= qty * cost
    return orders, budget


def _market_actions(obs, farm, opponent, private):
    day = int(_get(obs, "day", 0))
    hour = int(_get(obs, "hour", 0))
    money = float(farm.get("money", 0.0))

    desired = _desired_hands(farm, day)
    current_hires = int(farm.get("hires_today", len(farm.get("hands", []))))
    hire_needed = max(0, desired - current_hires)
    if hour == 0:
        hire_needed = min(hire_needed, 8)
    elif hour == 1:
        hire_needed = min(hire_needed, 6)

    hire_orders = []
    hire_cost = 0
    for offset in range(hire_needed):
        cost = _fib_hire_cost(current_hires + offset)
        if hire_cost + cost > max(0, money - 200):
            break
        hire_cost += cost
        hire_orders.append(["HIRE"])

    non_hire_capacity = max(0, 10 - len(hire_orders))
    non_hire = []

    # At the morning hiring burst reserve one slot for feed; later turns can
    # release several products without blocking reinvestment orders.
    sell_limit = 1 if hour == 0 else 4
    for order in _sell_orders(obs, private)[:sell_limit]:
        if len(non_hire) >= non_hire_capacity:
            break
        non_hire.append(order)

    budget = max(0.0, money - hire_cost)
    feed_order, budget = _feed_order(obs, farm, private, budget)
    if feed_order and len(non_hire) < non_hire_capacity:
        non_hire.append(feed_order)

    animal_orders, budget = _animal_orders(obs, farm, opponent, private, budget)
    for order in animal_orders:
        if len(non_hire) >= non_hire_capacity:
            break
        non_hire.append(order)

    unlocked = len(farm.get("unlocked_quadrants", ["NW"]))
    opponent_unlocked = len(opponent.get("unlocked_quadrants", ["NW"]))
    land_costs = (1000, 2000, 4000)
    occupied = sum(
        1
        for x, y in _unlocked_cells(farm)
        if farm["tiles"][y][x] is not None
    )
    land_start = LAND_START_DAY.get(unlocked, 99)
    land_force = LAND_FORCE_DAY.get(unlocked, 99)
    land_occupancy = LAND_OCCUPANCY.get(unlocked, 1.0)
    land_reserve = LAND_CASH_RESERVE.get(unlocked, 999999)
    if (
        unlocked < LAND_MAX_QUADRANTS
        and day >= land_start
        and len(non_hire) < non_hire_capacity
        and (
            occupied >= int(len(_unlocked_cells(farm)) * land_occupancy)
            or (day >= 10 and opponent_unlocked > unlocked)
            or day >= land_force
        )
        and budget >= land_costs[unlocked - 1] + land_reserve
    ):
        non_hire.append(["BUY_LAND"])
        budget -= land_costs[unlocked - 1]

    for order in _seed_orders(obs, farm, opponent, private, budget):
        if len(non_hire) >= non_hire_capacity:
            break
        non_hire.append(order)
        budget -= CROPS[order[1]]["seed"] * int(order[2])

    return (non_hire + hire_orders)[:10]


def agent(obs):
    farms = _get(obs, "farms", []) or []
    player = int(_get(obs, "player", 0))
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    opponent = farms[1 - player] if len(farms) > 1 else farm
    private = _as_dict(_get(obs, "private", {}))
    farmer_action, hand_actions = _worker_actions(obs, farm, opponent, private)
    market_actions = _market_actions(obs, farm, opponent, private)
    return {
        "farmer": farmer_action,
        "hands": hand_actions,
        "market": market_actions,
    }
