from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-changes", type=int, required=True)
    args = parser.parse_args()
    markdown = args.input.read_text(encoding="utf-8")
    changes = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changes
        text = match.group(1)
        tokens = text.split()
        if len(tokens) > 1 and len(set(tokens)) == 1:
            changes += 1
            return f"<td>{tokens[0]}</td>"
        return match.group(0)

    result = re.sub(r"<td>([^<>]*)</td>", replace, markdown)
    if changes != args.expected_changes:
        raise ValueError(
            f"expected {args.expected_changes} duplicate cells, found {changes}"
        )
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    print(f"{args.output} changes={changes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
