"""Inspect the public Kaggriculture top-episode dataset metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEPS = Path(__file__).resolve().parents[1] / "deps"
sys.path.insert(0, str(DEPS))

import requests  # noqa: E402


INDEX_SLUG = "kaggriculture-episodes-index"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        help="Inspect a daily dataset such as 2026-08-15 instead of the index.",
    )
    args = parser.parse_args()
    slug = f"kaggriculture-episodes-{args.date}" if args.date else INDEX_SLUG
    url = f"https://www.kaggle.com/api/v1/datasets/view/kaggle/{slug}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.json()
    files = data.get("files", [])
    summary = {
        "keys": sorted(data),
        "title": data.get("title"),
        "last_updated": data.get("lastUpdated"),
        "total_bytes": data.get("totalBytes"),
        "file_count": len(files),
        "files": [
            {
                "name": item.get("name"),
                "total_bytes": item.get("totalBytes"),
                "creation_date": item.get("creationDate"),
            }
            for item in files
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
