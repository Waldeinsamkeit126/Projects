param(
    [Parameter(Mandatory = $true)]
    [string]$EpisodeDirectory,

    [string]$PlayerName = "KAKA Minishijie",

    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$checkpointDays = @(0, 5, 7, 10, 15, 20, 25, 29)

function Get-FarmSummary {
    param(
        [Parameter(Mandatory = $true)]$Observation,
        [Parameter(Mandatory = $true)][int]$PlayerIndex
    )

    $farm = $Observation.farms[$PlayerIndex]
    $cropCounts = @{}
    $animalCounts = @{}
    $unfed = 0
    $uncared = 0

    foreach ($row in $farm.tiles) {
        foreach ($tile in $row) {
            if ($null -eq $tile -or $tile -is [string]) {
                continue
            }
            if ($tile.crop) {
                $crop = [string]$tile.crop
                $cropCounts[$crop] = 1 + [int]($cropCounts[$crop] ?? 0)
            }
            if ($tile.animal) {
                $animal = [string]$tile.animal
                $animalCounts[$animal] = 1 + [int]($animalCounts[$animal] ?? 0)
                if ([int]$tile.consecutive_unfed -gt 0) { $unfed++ }
                if (-not [bool]$tile.cared_today) { $uncared++ }
            }
        }
    }

    [ordered]@{
        money = [math]::Round([double]$farm.money, 3)
        hands = @($farm.hands).Count
        land = @($farm.unlocked_quadrants).Count
        crops = [ordered]@{
            WHEAT = [int]($cropCounts["WHEAT"] ?? 0)
            MELON = [int]($cropCounts["MELON"] ?? 0)
            STRAWBERRY = [int]($cropCounts["STRAWBERRY"] ?? 0)
            CARROT = [int]($cropCounts["CARROT"] ?? 0)
            TOMATO = [int]($cropCounts["TOMATO"] ?? 0)
        }
        animals = [ordered]@{
            COW = [int]($animalCounts["COW"] ?? 0)
            SHEEP = [int]($animalCounts["SHEEP"] ?? 0)
            GOOSE = [int]($animalCounts["GOOSE"] ?? 0)
        }
        unfed = $unfed
        uncared = $uncared
    }
}

function Get-CheckpointSummary {
    param(
        [Parameter(Mandatory = $true)]$Episode,
        [Parameter(Mandatory = $true)][int]$PlayerIndex
    )

    $lastByDay = @{}
    foreach ($step in $Episode.steps) {
        $observation = $step[$PlayerIndex].observation
        $lastByDay[[int]$observation.day] = $observation
    }

    $output = [ordered]@{}
    foreach ($day in $checkpointDays) {
        if ($lastByDay.ContainsKey($day)) {
            $output[[string]$day] = Get-FarmSummary -Observation $lastByDay[$day] -PlayerIndex $PlayerIndex
        }
    }
    $output
}

function Get-Branch {
    param(
        [Parameter(Mandatory = $true)]$Episode,
        [Parameter(Mandatory = $true)][int]$PlayerIndex
    )

    $decisionIndex = [math]::Min(168, $Episode.steps.Count - 1)
    $shops = @($Episode.steps[$decisionIndex][$PlayerIndex].observation.town.unlocked_shops)
    $dominated = $shops.Count -ge 2 -and $shops[0] -eq "ICE_CREAM_SHOP" -and $shops[1] -eq "YARN_STORE"
    $branch = if ($shops -contains "YARN_STORE" -and -not $dominated) { "high" } else { "low" }
    [ordered]@{ branch = $branch; shops = $shops }
}

function Get-Mean {
    param([object[]]$Values)
    $numbers = @($Values | Where-Object { $null -ne $_ } | ForEach-Object { [double]$_ })
    if ($numbers.Count -eq 0) { return $null }
    [math]::Round(($numbers | Measure-Object -Average).Average, 3)
}

$episodes = @()
$files = Get-ChildItem -LiteralPath $EpisodeDirectory -Filter "*.json" | Sort-Object Name
foreach ($file in $files) {
    $episode = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
    $names = @($episode.info.Agents | ForEach-Object { [string]$_.Name })
    $playerIndex = [array]::IndexOf($names, $PlayerName)
    if ($playerIndex -lt 0) { continue }
    $opponentIndex = 1 - $playerIndex
    $playerReward = [double]$episode.rewards[$playerIndex]
    $opponentReward = [double]$episode.rewards[$opponentIndex]
    $branchInfo = Get-Branch -Episode $episode -PlayerIndex $playerIndex

    $episodes += [ordered]@{
        episode_id = [int64]$episode.info.EpisodeId
        seed = [int64]$episode.info.seed
        seat = $playerIndex
        opponent = $names[$opponentIndex]
        result = if ($playerReward -gt $opponentReward) { "win" } elseif ($playerReward -lt $opponentReward) { "loss" } else { "tie" }
        player_reward = $playerReward
        opponent_reward = $opponentReward
        margin = $playerReward - $opponentReward
        branch = $branchInfo.branch
        shops = $branchInfo.shops
        player = Get-CheckpointSummary -Episode $episode -PlayerIndex $playerIndex
        opponent_state = Get-CheckpointSummary -Episode $episode -PlayerIndex $opponentIndex
    }
}

$groups = [ordered]@{}
foreach ($groupName in @("all", "win", "loss", "high", "low")) {
    $rows = switch ($groupName) {
        "all" { @($episodes) }
        "win" { @($episodes | Where-Object { $_.result -eq "win" }) }
        "loss" { @($episodes | Where-Object { $_.result -eq "loss" }) }
        default { @($episodes | Where-Object { $_.branch -eq $groupName }) }
    }
    if ($rows.Count -eq 0) { continue }
    $groups[$groupName] = [ordered]@{
        games = $rows.Count
        player_reward_mean = Get-Mean @($rows | ForEach-Object { $_.player_reward })
        opponent_reward_mean = Get-Mean @($rows | ForEach-Object { $_.opponent_reward })
        margin_mean = Get-Mean @($rows | ForEach-Object { $_.margin })
        day15_money_mean = Get-Mean @($rows | ForEach-Object { $_.player["15"].money })
        day15_strawberry_mean = Get-Mean @($rows | ForEach-Object { $_.player["15"].crops.STRAWBERRY })
        day15_cows_mean = Get-Mean @($rows | ForEach-Object { $_.player["15"].animals.COW })
        day15_sheep_mean = Get-Mean @($rows | ForEach-Object { $_.player["15"].animals.SHEEP })
    }
}

$report = [ordered]@{
    player = $PlayerName
    episode_count = $episodes.Count
    wins = @($episodes | Where-Object { $_.result -eq "win" }).Count
    losses = @($episodes | Where-Object { $_.result -eq "loss" }).Count
    ties = @($episodes | Where-Object { $_.result -eq "tie" }).Count
    groups = $groups
    episodes = @($episodes | Sort-Object episode_id -Descending)
}

$payload = $report | ConvertTo-Json -Depth 12
if ($OutputPath) {
    $outputDirectory = Split-Path -Parent $OutputPath
    if ($outputDirectory) { New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null }
    Set-Content -LiteralPath $OutputPath -Value $payload -Encoding utf8
}
$payload
