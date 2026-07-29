from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.score import _TableParser  # noqa: E402
from audit_two_triangular_integer_tables import parse_tables  # noqa: E402


OCR_DIGIT_TRANSLATION = str.maketrans(
    {
        "A": "4",
        "Z": "7",
        "z": "7",
        "L": "1",
        "l": "1",
        "I": "1",
        "i": "1",
        "J": "1",
        "f": "1",
        "d": "4",
        "g": "9",
        "s": "5",
        "E": "8",
        "O": "0",
        "o": "0",
        "M": "4",
    }
)


def parse_one(path: Path) -> _TableParser:
    parsed = _TableParser()
    parsed.feed(path.read_text(encoding="utf-8"))
    if parsed.tables != 1:
        raise ValueError(f"expected one OCR table in {path}, got {parsed.tables}")
    return parsed


def digits(value: str) -> str:
    return re.sub(r"[^0-9]", "", value)


def normalized_ocr_digits(value: str) -> str:
    return digits(value.translate(OCR_DIGIT_TRANSLATION))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr", type=Path, required=True)
    parser.add_argument("--gt", type=Path, required=True)
    parser.add_argument("--gt-table-index", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ocr = parse_one(args.ocr)
    gt_tables = parse_tables(args.gt.read_text(encoding="utf-8"))
    gt = gt_tables[args.gt_table_index]
    ocr_rows = ocr.cell_text_rows
    gt_rows = gt.cell_text_rows
    if len(ocr_rows) != len(gt_rows):
        raise ValueError(f"row mismatch: OCR={len(ocr_rows)} GT={len(gt_rows)}")
    if any(len(row) + 1 != len(expected) for row, expected in zip(ocr_rows, gt_rows)):
        raise ValueError("OCR numeric rows must be exactly one column narrower than GT")

    inferred: defaultdict[str, Counter[str]] = defaultdict(Counter)
    exact = 0
    numeric_cells = 0
    restored_dashes = 0
    missing: list[dict[str, object]] = []
    overflow: list[dict[str, object]] = []
    mismatches: list[dict[str, object]] = []
    for row_index, (row, expected_row) in enumerate(zip(ocr_rows, gt_rows)):
        for column_index, (raw, expected) in enumerate(zip(row, expected_row[1:])):
            raw = raw.strip()
            expected = expected.strip()
            if not expected:
                if raw:
                    overflow.append(
                        {"row": row_index, "column": column_index, "raw": raw}
                    )
                continue
            if expected == "-":
                if not raw:
                    restored_dashes += 1
                elif raw != "-":
                    mismatches.append(
                        {
                            "row": row_index,
                            "column": column_index,
                            "raw": raw,
                            "expected": expected,
                            "normalized": normalized_ocr_digits(raw),
                        }
                    )
                continue
            numeric_cells += 1
            if not raw:
                missing.append(
                    {"row": row_index, "column": column_index, "expected": expected}
                )
                continue
            raw_alnum = "".join(character for character in raw if character.isalnum())
            expected_digits = digits(expected)
            if len(raw_alnum) == len(expected_digits):
                for source, target in zip(raw_alnum, expected_digits):
                    if not source.isdigit():
                        inferred[source][target] += 1
            normalized = normalized_ocr_digits(raw)
            if normalized == expected_digits:
                exact += 1
            else:
                mismatches.append(
                    {
                        "row": row_index,
                        "column": column_index,
                        "raw": raw,
                        "expected": expected,
                        "normalized": normalized,
                    }
                )
    result = {
        "ocr": str(args.ocr),
        "gt": str(args.gt),
        "rows": len(ocr_rows),
        "ocr_columns": sorted(set(map(len, ocr.rows))),
        "gt_columns": sorted(set(map(len, gt.rows))),
        "numeric_cells": numeric_cells,
        "exact_numeric_cells": exact,
        "exact_numeric_rate": exact / max(1, numeric_cells),
        "restored_dashes": restored_dashes,
        "missing": missing,
        "overflow": overflow,
        "mismatches": mismatches,
        "inferred_letter_mappings": {
            source: counts.most_common() for source, counts in sorted(inferred.items())
        },
    }
    result["structure_ok"] = not missing and not overflow
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "rows": result["rows"],
                "numeric_cells": numeric_cells,
                "exact_numeric_cells": exact,
                "exact_numeric_rate": result["exact_numeric_rate"],
                "restored_dashes": restored_dashes,
                "missing": len(missing),
                "overflow": len(overflow),
                "mismatches": len(mismatches),
                "inferred_letter_mappings": result["inferred_letter_mappings"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
