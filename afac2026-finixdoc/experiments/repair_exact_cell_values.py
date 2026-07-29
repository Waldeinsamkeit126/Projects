from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replace", action="append", default=[])
    args = parser.parse_args()
    replacements: list[tuple[str, str]] = []
    for item in args.replace:
        if "=" not in item:
            raise ValueError(f"replacement must be OLD=NEW: {item!r}")
        old, new = item.split("=", 1)
        replacements.append((old, new))
    if not replacements:
        raise ValueError("at least one replacement is required")

    markdown = args.input.read_text(encoding="utf-8")
    for old, new in replacements:
        pattern = f"<td>{html.escape(old)}</td>"
        count = markdown.count(pattern)
        if count != 1:
            raise ValueError(f"expected one exact cell {old!r}, found {count}")
        markdown = markdown.replace(pattern, f"<td>{html.escape(new)}</td>", 1)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(markdown, encoding="utf-8")
    temporary.replace(args.output)
    print(f"{args.output} changes={len(replacements)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
