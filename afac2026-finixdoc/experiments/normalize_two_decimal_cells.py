from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-leading-rows", type=int, default=1)
    parser.add_argument("--skip-leading-columns", type=int, default=4)
    parser.add_argument("--expected-changes", type=int, required=True)
    args = parser.parse_args()

    markdown = args.input.read_text(encoding="utf-8")
    row_pattern = re.compile(r"^(?P<indent>[ \t]*)<tr>(?P<body>.*?)</tr>$", re.M)
    matches = list(row_pattern.finditer(markdown))
    replacements: list[tuple[int, int, str]] = []
    changes = 0
    anomalies: list[tuple[int, int, str]] = []
    for row_index, match in enumerate(matches):
        if row_index < args.skip_leading_rows:
            continue
        cells = re.findall(r"<td>(.*?)</td>", match.group("body"))
        for column_index, value in enumerate(cells):
            if column_index < args.skip_leading_columns or not value.strip():
                continue
            if re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
                continue
            if re.fullmatch(r"[0-9\s,.:，。]+", value):
                digits = re.sub(r"\D", "", value)
                if len(digits) >= 3:
                    normalized = f"{digits[:-2]}.{digits[-2:]}"
                elif digits == "0":
                    normalized = "0.00"
                else:
                    anomalies.append((row_index, column_index, value))
                    continue
                if normalized != value:
                    cells[column_index] = normalized
                    changes += 1
            else:
                anomalies.append((row_index, column_index, value))
        rendered = match.group("indent") + "<tr>" + "".join(
            f"<td>{html.escape(cell)}</td>" for cell in cells
        ) + "</tr>"
        replacements.append((match.start(), match.end(), rendered))
    if changes != args.expected_changes:
        raise ValueError(f"expected {args.expected_changes} changes, found {changes}")
    if anomalies:
        raise ValueError(f"unrepairable numeric cells: {anomalies[:20]}")

    result = markdown
    for start, end, rendered in reversed(replacements):
        result = result[:start] + rendered + result[end:]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    print(f"{args.output} changes={changes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
