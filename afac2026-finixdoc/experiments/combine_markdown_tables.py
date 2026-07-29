from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parts = [path.read_text(encoding="utf-8").strip() for path in args.inputs]
    if any(not part.startswith("<table") or not part.endswith("</table>") for part in parts):
        raise ValueError("every input must contain one bare table")
    result = "\n\n".join(parts) + "\n"
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    print(f"{args.output} tables={len(parts)} characters={len(result.rstrip())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
