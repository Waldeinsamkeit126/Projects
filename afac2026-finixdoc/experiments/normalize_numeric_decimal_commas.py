from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.score import diagnose  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-changes", type=int, required=True)
    parser.add_argument("--ground-truth", type=Path)
    args = parser.parse_args()

    markdown = args.input.read_text(encoding="utf-8")
    changes = 0

    def normalize_cell(match: re.Match[str]) -> str:
        nonlocal changes
        value = match.group(1)
        normalized, count = re.subn(r"(?<=\d),(?=\d)", ".", value)
        changes += count
        return f"<td>{normalized}</td>"

    result = re.sub(r"<td>([^<>]*)</td>", normalize_cell, markdown)
    if changes != args.expected_changes:
        raise ValueError(
            f"expected {args.expected_changes} decimal commas, found {changes}"
        )

    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(result, encoding="utf-8")
    temporary.replace(args.output)
    report: dict[str, object] = {
        "input": str(args.input),
        "output": str(args.output),
        "changes": changes,
    }
    if args.ground_truth:
        ground_truth = args.ground_truth.read_text(encoding="utf-8")
        report["before"] = diagnose(markdown, ground_truth).to_dict()
        report["after"] = diagnose(result, ground_truth).to_dict()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
