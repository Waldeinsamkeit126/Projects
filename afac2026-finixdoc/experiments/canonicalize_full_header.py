from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixed-label", action="append", default=[])
    parser.add_argument("--numbered-cells", type=int, required=True)
    parser.add_argument("--number-template", default="{number}")
    parser.add_argument("--prefix-line", action="append", default=[])
    parser.add_argument("--merge-first-two", action="store_true")
    parser.add_argument("--skip-leading-rows", type=int, default=0)
    args = parser.parse_args()
    if args.numbered_cells < 1:
        raise ValueError("numbered cells must be positive")
    if args.skip_leading_rows < 0:
        raise ValueError("skip-leading-rows must be non-negative")
    try:
        numbered = [
            args.number_template.format(number=number)
            for number in range(1, args.numbered_cells + 1)
        ]
    except (IndexError, KeyError, ValueError) as error:
        raise ValueError(
            "number-template must contain a valid {number} placeholder"
        ) from error
    labels = [*args.fixed_label, *numbered]
    markdown = args.input.read_text(encoding="utf-8")
    row = "      <tr>" + "".join(
        f"<td>{html.escape(label)}</td>" for label in labels
    )
    row += "</tr>"
    row_matches = list(
        re.finditer(r"^[ \t]*<tr>.*?</tr>$", markdown, flags=re.M)
    )
    replaced_rows = args.skip_leading_rows + (2 if args.merge_first_two else 1)
    if len(row_matches) < replaced_rows:
        raise ValueError(
            f"expected at least {replaced_rows} rows, found {len(row_matches)}"
        )
    start = row_matches[0].start()
    end = row_matches[replaced_rows - 1].end()
    result = markdown[:start] + row + markdown[end:]
    if args.prefix_line:
        prefix = "\n".join(args.prefix_line).rstrip() + "\n\n"
        table_index = result.find("<table")
        if table_index < 0:
            raise ValueError("table start not found")
        result = prefix + result[table_index:]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
