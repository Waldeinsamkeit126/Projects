"""Print a compact cross-episode table from static-meta summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DAYS = (0, 5, 7, 10, 14, 15, 20, 25, 29)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    episodes = json.loads(args.report.read_text(encoding="utf-8"))
    for episode in episodes:
        print(f"EP {episode['episode_id']} seed={episode['seed']}")
        for player in episode["players"]:
            print(f"  {player['name']} reward={player['reward']:.0f}")
            for day in DAYS:
                row = player["days"].get(str(day))
                if not row:
                    continue
                state = row["end"]
                crops = ",".join(f"{k}={v}" for k, v in state["crops"].items()) or "-"
                animals = ",".join(f"{k}={v}" for k, v in state["animals"].items()) or "-"
                print(
                    f"    d{day:02d} money={state['money']:7.0f} "
                    f"hands={state['hands']:2d} land={state['land']} "
                    f"crops[{crops}] animals[{animals}]"
                )


if __name__ == "__main__":
    main()
