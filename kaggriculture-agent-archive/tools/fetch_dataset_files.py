"""Download named files from a public Kaggle dataset without CLI auth."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


DEPS = Path(__file__).resolve().parents[1] / "deps"
sys.path.insert(0, str(DEPS))

import requests  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="Dataset slug in owner/name form.")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    owner, slug = args.dataset.split("/", 1)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in args.files:
        url = f"https://www.kaggle.com/api/v1/datasets/download/{owner}/{slug}/{name}"
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        output = args.out_dir / Path(name).name
        output.write_bytes(response.content)
        rows.append(
            {
                "name": name,
                "output": str(output),
                "bytes": len(response.content),
                "sha256": hashlib.sha256(response.content).hexdigest(),
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
