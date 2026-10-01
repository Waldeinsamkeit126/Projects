"""Fetch and summarize public Kaggriculture episode replays."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


DEPS = Path(__file__).resolve().parents[1] / "deps"
sys.path.insert(0, str(DEPS))

import requests  # noqa: E402


def fetch_episode(episode_id: int, out_dir: Path) -> Path:
    url = f"https://www.kaggleusercontent.com/episodes/{episode_id}.json"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"episode-{episode_id}.json"
    output.write_bytes(response.content)
    return output


def summarize(path: Path) -> dict:
    episode = json.loads(path.read_text(encoding="utf-8"))
    agents = episode.get("info", {}).get("Agents", [])
    names = [agent.get("Name") for agent in agents]
    return {
        "episode_id": episode.get("info", {}).get("EpisodeId"),
        "seed": episode.get("info", {}).get("seed"),
        "agents": names,
        "rewards": episode.get("rewards"),
        "steps": len(episode.get("steps", [])),
    }


def discover_episode_ids(submission_id: int) -> list[int]:
    url = (
        "https://www.kaggle.com/competitions/kaggriculture/submissions"
        f"?submissionId={submission_id}"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    patterns = [
        r"episodeId[\\\"'=: ]+(\\d+)",
        r"episode-id[\\\"'=: ]+(\\d+)",
    ]
    ids: set[int] = set()
    for pattern in patterns:
        ids.update(int(value) for value in re.findall(pattern, response.text))
    return sorted(ids)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_ids", nargs="*", type=int)
    parser.add_argument("--submission-id", type=int)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "online_episodes",
    )
    args = parser.parse_args()

    episode_ids = list(args.episode_ids)
    if args.submission_id:
        discovered = discover_episode_ids(args.submission_id)
        print(f"discovered={discovered}")
        episode_ids.extend(discovered)

    summaries = []
    for episode_id in sorted(set(episode_ids)):
        output = fetch_episode(episode_id, args.out_dir)
        summaries.append(summarize(output))
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
