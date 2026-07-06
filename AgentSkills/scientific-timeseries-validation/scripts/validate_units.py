#!/usr/bin/env python3
"""Validate an explicit unit conversion and optionally write a converted CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


LINEAR_UNITS = {
    "time": {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1.0, "min": 60.0, "h": 3600.0, "day": 86400.0, "d": 86400.0},
    "frequency": {"hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9},
    "voltage": {"uv": 1e-6, "µv": 1e-6, "mv": 1e-3, "v": 1.0, "kv": 1e3},
    "length": {"um": 1e-6, "µm": 1e-6, "mm": 1e-3, "cm": 1e-2, "m": 1.0, "km": 1e3},
}


def emit_error(reason: str, detail: str, code: int = 2) -> None:
    print(json.dumps({"status": "error", "reason": reason, "detail": detail}))
    raise SystemExit(code)


def normalize(unit: str) -> str:
    return unit.strip().replace("μ", "µ").lower()


def category(unit: str) -> str | None:
    normalized = normalize(unit)
    if normalized in {"c", "°c", "k", "f", "°f"}:
        return "temperature"
    for name, units in LINEAR_UNITS.items():
        if normalized in units:
            return name
    return None


def temperature_to_kelvin(value: float, unit: str) -> float:
    unit = normalize(unit)
    if unit in {"c", "°c"}:
        return value + 273.15
    if unit == "k":
        return value
    if unit in {"f", "°f"}:
        return (value - 32.0) * 5.0 / 9.0 + 273.15
    raise ValueError(unit)


def kelvin_to_temperature(value: float, unit: str) -> float:
    unit = normalize(unit)
    if unit in {"c", "°c"}:
        return value - 273.15
    if unit == "k":
        return value
    if unit in {"f", "°f"}:
        return (value - 273.15) * 9.0 / 5.0 + 32.0
    raise ValueError(unit)


def convert(value: float, source: str, target: str) -> float:
    source_category = category(source)
    target_category = category(target)
    if source_category is None or target_category is None:
        raise ValueError("unsupported_unit")
    if source_category != target_category:
        raise ValueError("incompatible_units")
    if source_category == "temperature":
        return kelvin_to_temperature(temperature_to_kelvin(value, source), target)
    units = LINEAR_UNITS[source_category]
    return value * units[normalize(source)] / units[normalize(target)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--column", "--time-column", dest="column", required=True)
    parser.add_argument("--from-unit", "--time-unit", dest="from_unit", required=True)
    parser.add_argument("--to-unit", "--convert-time-to", dest="to_unit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not args.input.is_file():
        emit_error("file_not_found", str(args.input))
    if args.input.suffix.lower() not in {".csv", ".tsv", ".txt"}:
        emit_error(
            "unsupported_format",
            "Unit conversion writes a new delimited file and accepts CSV/TSV text input.",
        )
    source_category = category(args.from_unit)
    target_category = category(args.to_unit)
    if source_category is None or target_category is None:
        emit_error("unsupported_unit", f"{args.from_unit} -> {args.to_unit}")
    if source_category != target_category:
        emit_error("incompatible_units", f"{args.from_unit} -> {args.to_unit}")

    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames or args.column not in reader.fieldnames:
            emit_error("column_not_found", args.column)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    converted = 0
    missing = 0
    invalid: list[int] = []
    output_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(rows, start=2):
        text = (row.get(args.column) or "").strip()
        if text.lower() in {"", "na", "n/a", "nan", "null", "none"}:
            missing += 1
            output_rows.append(row)
            continue
        try:
            value = float(text)
            if not math.isfinite(value):
                raise ValueError
            converted_value = convert(value, args.from_unit, args.to_unit)
        except ValueError:
            invalid.append(row_number)
            output_rows.append(row)
            continue
        updated = dict(row)
        updated[args.column] = format(converted_value, ".15g")
        output_rows.append(updated)
        converted += 1

    if invalid:
        emit_error("non_numeric_values", f"Rows: {invalid[:20]}")

    if args.output:
        if args.output.resolve() == args.input.resolve():
            emit_error("overwrite_refused", "Choose a new --output path to preserve the original.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)

    sample_factor = None
    if source_category != "temperature":
        sample_factor = LINEAR_UNITS[source_category][normalize(args.from_unit)] / LINEAR_UNITS[source_category][normalize(args.to_unit)]
    result = {
        "status": "valid",
        "column": args.column,
        "quantity": source_category,
        "original_unit": args.from_unit,
        "normalized_unit": args.to_unit,
        "conversion_factor": sample_factor,
        "converted_rows": converted,
        "missing_rows_unchanged": missing,
        "output": str(args.output) if args.output else None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
