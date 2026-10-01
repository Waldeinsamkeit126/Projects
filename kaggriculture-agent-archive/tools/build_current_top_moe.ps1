param(
    [string]$TopEpisodeDirectory = "work\kaggriculture_agent\datasets\episodes_2026-08-15\top8",
    [string]$BaseAgentPath = "outputs\kaggriculture_agent\public_indar_market_v1\main.py",
    [string]$OutputDirectory = "work\kaggriculture_agent\candidates\current_top_moe_v1"
)

$ErrorActionPreference = "Stop"

function Get-ActionJson {
    param($Action)
    $Action | ConvertTo-Json -Depth 10 -Compress
}

function Get-ConsensusRouteJson {
    param(
        [Parameter(Mandatory = $true)][object[]]$Sources
    )

    $episodes = foreach ($source in $Sources) {
        $path = Join-Path $TopEpisodeDirectory ("{0}.json" -f $source.Episode)
        [pscustomobject]@{
            Episode = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
            Seat = [int]$source.Seat
        }
    }

    $route = New-Object System.Collections.Generic.List[string]
    foreach ($runtimeStep in 0..719) {
        $replayStep = [math]::Min($runtimeStep + 1, 719)
        $options = foreach ($source in $episodes) {
            Get-ActionJson $source.Episode.steps[$replayStep][$source.Seat].action
        }
        $winner = $options |
            Group-Object |
            Sort-Object @{ Expression = "Count"; Descending = $true }, @{ Expression = { [array]::IndexOf($options, $_.Name) }; Descending = $false } |
            Select-Object -First 1
        $route.Add([string]$winner.Name)
    }
    "[" + ($route -join ",") + "]"
}

# Thomas Tschinkel and カワシギ were the two approximately 3200-rated agents in
# the 2026-08-15 public top episodes. Use Thomas's stable seat-specific low
# routes (his two seat-1 traces agree at 645/720 actions), then use the observed
# Yarn-store route for each seat. カワシギ's low route is deliberately excluded
# from the seat-1 consensus because it branches heavily across non-Yarn shops.
$seat0Low = Get-ConsensusRouteJson -Sources @(
    @{ Episode = 93221407; Seat = 0 },
    @{ Episode = 93212493; Seat = 0 },
    @{ Episode = 93238403; Seat = 0 },
    @{ Episode = 93273309; Seat = 0 }
)
$seat0High = Get-ConsensusRouteJson -Sources @(
    @{ Episode = 93247305; Seat = 0 }
)
$seat1Low = Get-ConsensusRouteJson -Sources @(
    @{ Episode = 93454366; Seat = 1 },
    @{ Episode = 93448154; Seat = 1 }
)
$seat1High = Get-ConsensusRouteJson -Sources @(
    @{ Episode = 93247305; Seat = 1 }
)

$baseAgent = Get-Content -LiteralPath $BaseAgentPath -Raw
$suffix = @'


# --- E300 current-pool seat-aware demand MoE ---
# Generated from the 2026-08-15 public top-episode consensus. Replay step 1 is
# runtime step 0; the last replay action is repeated for runtime step 719.
_E300_SEAT0_LOW = json.loads(r'''__SEAT0_LOW__''')
_E300_SEAT0_HIGH = json.loads(r'''__SEAT0_HIGH__''')
_E300_SEAT1_LOW = json.loads(r'''__SEAT1_LOW__''')
_E300_SEAT1_HIGH = json.loads(r'''__SEAT1_HIGH__''')
_E300_STATE = {
    0: {"last_step": -1, "shops": (), "expert": None},
    1: {"last_step": -1, "shops": (), "expert": None},
}
__version__ = "E300-current-top-seat-demand-MoE-v1"


def _e300_route(obs):
    seat = _seat(obs)
    step = _e279_step(obs)
    state = _E300_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {"last_step": step, "shops": (), "expert": None}
        _E300_STATE[seat] = state
    state["last_step"] = step
    if step <= _E279_DECISION_STEP:
        state["shops"] = _e279_shops(obs)
    if state.get("expert") is None and step >= _E279_DECISION_STEP:
        shops = tuple(state.get("shops") or ())
        dominated = (
            len(shops) >= 2
            and shops[0] == "ICE_CREAM_SHOP"
            and shops[1] == "YARN_STORE"
        )
        state["expert"] = "high" if "YARN_STORE" in shops and not dominated else "low"
    high = state.get("expert") == "high"
    if seat == 0:
        return _E300_SEAT0_HIGH if high else _E300_SEAT0_LOW
    return _E300_SEAT1_HIGH if high else _E300_SEAT1_LOW


def _e300_agent(obs, configuration=None):
    del configuration
    global _ACTIONS
    try:
        route = _e300_route(obs)
        _ACTIONS = route
        step = min(max(0, int(_get(obs, "step", 0) or 0)), len(route) - 1)
        action = _weed_repair_action(obs, _copy_action(route[step]), step)
        action = _v17_feed_guard(obs, action, step)
        action = _v17_room_evac(obs, action, step)
        action = _rank_sell_slots(obs, action, None)
        action = _v17_room_guard(obs, action, step)
        action = _terminal_liquidation(obs, action, step)
        return _align_hands(action, obs)
    except Exception:
        farm = _farm(obs, _seat(obs))
        return {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in (_get(farm, "hands", []) or [])],
            "market": [],
        }


agent = _e300_agent


def _kaggle_submission_entrypoint(obs):
    return agent(obs)
'@

$suffix = $suffix.Replace("__SEAT0_LOW__", $seat0Low)
$suffix = $suffix.Replace("__SEAT0_HIGH__", $seat0High)
$suffix = $suffix.Replace("__SEAT1_LOW__", $seat1Low)
$suffix = $suffix.Replace("__SEAT1_HIGH__", $seat1High)

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$outputPath = Join-Path $OutputDirectory "main.py"
[System.IO.File]::WriteAllText($outputPath, $baseAgent + $suffix, [System.Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    output = $outputPath
    bytes = (Get-Item -LiteralPath $outputPath).Length
    seat0_low_sources = 4
    seat0_high_sources = 1
    seat1_low_sources = 2
    seat1_high_sources = 1
} | ConvertTo-Json
