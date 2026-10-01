"""Kaggriculture competition agent.

The agent is deliberately dependency-free so this file can be submitted directly
to Kaggle.  It combines four ideas:

* cheap daily farm hands for parallel work;
* deterministic task assignment and shortest-path routing;
* a diversified, opponent-aware crop portfolio;
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
        "max_yield": 4,
        "ongoing": False,
    },
    "CARROT": {
        "seed": 20,
        "first": 2,
        "max_day": 3,
        "max_yield": 3,
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
    "MELON": 12,
    "EGG": 40,
    "MILK": 3,
    "WOOL": 3,
    "FERTILIZER": 10,
}

CROWD_RISK = {
    "MELON": 3.0,
    "STRAWBERRY": 2.4,
    "TOMATO": 1.1,
    "CARROT": 0.55,
    "WHEAT": 0.20,
}

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


def _phase_weights(day):
    # Leave enough time on days 28-29 to turn inventory into banked coins.
    if day <= 18:
        return {
            "MELON": 0.62,
            "CARROT": 0.1596,
            "WHEAT": 0.1406,
            "TOMATO": 0.0798,
        }
    if day <= 26:
        return {"CARROT": 0.55, "WHEAT": 0.45}
    return {}


def _target_counts(obs, farm, opponent, cell_count):
    """Allocate a portfolio while reacting to prices and visible opponent crops."""
    weights = _phase_weights(int(_get(obs, "day", 0)))
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


def _crop_plan(obs, farm, opponent):
    """Return empty-cell -> desired-crop and aggregate seed requirements."""
    cells = _unlocked_cells(farm)
    targets = _target_counts(obs, farm, opponent, len(cells))
    current = _plant_counts(farm)
    remaining = {
        crop: max(0, targets.get(crop, 0) - current.get(crop, 0))
        for crop in CROPS
    }

    empties = [xy for xy in cells if farm["tiles"][xy[1]][xy[0]] is None]
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
                crop = crop_plan.get(xy)
                if hour <= 18 and crop and plant_allowance[crop] > 0:
                    tasks.append((4, xy, ["PLANT", crop]))
                    plant_allowance[crop] -= 1
                continue
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "WEED":
                tasks.append((3, xy, ["DIG"]))
                continue
            if tile.get("kind") != "PLANT":
                continue

            # On the liquidation days, realized inventory beats future yield.
            if day >= 28 and _ready_to_harvest(tile, day):
                tasks.append((0, xy, ["HARVEST"]))
            elif not tile.get("watered_today", False):
                urgent = 0 if tile.get("consecutive_unwatered", 0) >= 1 else 1
                tasks.append((urgent, xy, ["WATER"]))
            elif _ready_to_harvest(tile, day):
                tasks.append((2, xy, ["HARVEST"]))
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
    return any(int(inv.get(item, 0)) > 0 for item in PRODUCTS if item != "FERTILIZER")


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
    free_workers = []

    for idx, (pos, inv) in enumerate(zip(positions, inventories)):
        inv = _as_dict(inv)
        # Bring harvested goods home early enough to sell them the same day.
        if _inventory_has_sale(inv) and (hour <= 20 or day >= 28):
            if tuple(pos) in set(shed_goals):
                actions[idx] = ["DROP"]
            else:
                actions[idx] = _next_move(farm, pos, shed_goals, idx)
        else:
            free_workers.append(idx)

    available = list(tasks)
    unassigned = set(free_workers)
    # Global greedy matching is markedly better than letting every hand chase
    # the same nearest plant.  Task priority dominates travel distance.
    while unassigned and available:
        best = None
        for idx in unassigned:
            px, py = positions[idx]
            for task_index, (priority, (tx, ty), action) in enumerate(available):
                key = (priority, abs(px - tx) + abs(py - ty), idx, ty, tx)
                if best is None or key < best[0]:
                    best = (key, idx, task_index, (tx, ty), action)
        _, idx, task_index, target, task_action = best
        pos = tuple(positions[idx])
        actions[idx] = task_action if pos == target else _next_move(farm, pos, [target], idx)
        unassigned.remove(idx)
        available.pop(task_index)

    return actions[0], actions[1:]


def _fib_hire_cost(index):
    a, b = 1, 1
    for _ in range(index):
        a, b = b, a + b
    return a


def _desired_hands(farm, day):
    cells = _unlocked_cells(farm)
    active = sum(
        1
        for x, y in cells
        if farm["tiles"][y][x] is not None
    )
    # Newly purchased land should not immediately force us to pay for a
    # 100-tile workforce.  Scale with real work and keep an eight-hand floor
    # for the opening planting burst.
    workload = max(25, active)
    if workload <= 25:
        desired = 8
    elif workload <= 50:
        desired = 10
    elif workload <= 75:
        desired = 12
    else:
        desired = 13
    if day >= 29:
        desired = min(desired, 9)
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
    for _, crop, deficit in candidates:
        affordable = max(0, int((budget - reserve) // CROPS[crop]["seed"]))
        qty = min(deficit, affordable)
        if qty <= 0:
            continue
        orders.append(["BUY_SEED", crop, qty])
        budget -= qty * CROPS[crop]["seed"]
    return orders


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

    # Sales are placed first so their proceeds can fund later atomic orders.
    for order in _sell_orders(obs, private):
        if len(non_hire) >= non_hire_capacity:
            break
        non_hire.append(order)

    budget = max(0.0, money - hire_cost)
    unlocked = len(farm.get("unlocked_quadrants", ["NW"]))
    land_costs = (1000, 2000, 4000)
    if (
        day >= 8
        and unlocked < 4
        and len(non_hire) < non_hire_capacity
        and budget >= land_costs[unlocked - 1] + 1200
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
