from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixed-label", action="append", required=True)
    parser.add_argument("--span-label", required=True)
    parser.add_argument("--numbered-cells", type=int, required=True)
    args = parser.parse_args()
    if args.numbered_cells < 1:
        raise ValueError("numbered cells must be positive")
    markdown = args.input.read_text(encoding="utf-8")
    row0 = "      <tr>" + "".join(
        f'<td rowspan="2">{html.escape(label)}</td>'
        for label in args.fixed_label
    )
    row0 += (
        f'<td colspan="{args.numbered_cells}">'
        f"{html.escape(args.span_label)}</td></tr>"
    )
    row1 = "      <tr>" + "".join(
        f"<td>{number}</td>" for number in range(1, args.numbered_cells + 1)
    )
    row1 += "</tr>"
    replacement = iter((row0, row1))
    result, count = re.subn(
        r"^[ \t]*<tr>.*?</tr>$",
        lambda _: next(replacement),
        markdown,
        count=2,
        flags=re.M,
    )
    if count != 2:
        raise ValueError(f"expected two header rows, replaced {count}")
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
