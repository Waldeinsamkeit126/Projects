from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def parse_group(value: str) -> list[tuple[str, str, str, str]]:
    parts = value.split(":")
    if len(parts) != 4:
        raise ValueError(f"group must be PAYMENT:START:END:GENDERS: {value!r}")
    payment, start_text, end_text, genders = parts
    start, end = int(start_text), int(end_text)
    if start > end or not genders:
        raise ValueError(f"invalid group: {value!r}")
    return [
        ("终身", payment, str(age), gender)
        for age in range(start, end + 1)
        for gender in genders
    ]


def parse_trailing(value: str) -> tuple[str, str, str, str]:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"trailing key must be PAYMENT:AGE:GENDER: {value!r}")
    payment, age, gender = parts
    return "终身", payment, str(int(age)), gender


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--trailing", action="append", default=[])
    parser.add_argument("--expected-columns", type=int, required=True)
    args = parser.parse_args()

    expected = [key for value in args.group for key in parse_group(value)]
    expected.extend(parse_trailing(value) for value in args.trailing)
    markdown = args.input.read_text(encoding="utf-8")
    row_pattern = re.compile(r"^(?P<indent>[ \t]*)<tr>(?P<body>.*?)</tr>$", re.M)
    matches = list(row_pattern.finditer(markdown))
    if len(matches) != len(expected) + 1:
        raise ValueError(
            f"expected one header plus {len(expected)} data rows, "
            f"found {len(matches)} rows"
        )

    replacements: list[tuple[int, int, str]] = []
    changes = [0, 0, 0, 0]
    for index, (match, key) in enumerate(zip(matches[1:], expected), start=1):
        cells = re.findall(r"<td>(.*?)</td>", match.group("body"))
        if len(cells) != args.expected_columns:
            raise ValueError(f"row {index} has {len(cells)} cells")
        for column, value in enumerate(key):
            changes[column] += cells[column] != value
            cells[column] = value
        rendered = match.group("indent") + "<tr>" + "".join(
            f"<td>{html.escape(cell)}</td>" for cell in cells
        ) + "</tr>"
        replacements.append((match.start(), match.end(), rendered))

    result = markdown
    for start, end, rendered in reversed(replacements):
        result = result[:start] + rendered + result[end:]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    print(
        f"{args.output} rows={len(expected)} key_changes={changes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
