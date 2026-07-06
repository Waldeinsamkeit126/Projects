#!/usr/bin/env python3
"""Diagnose timestamp ordering, jitter, gaps, sample rate, and Nyquist limits."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
from pathlib import Path


TIME_FACTORS = {
    "ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1.0,
    "min": 60.0, "h": 3600.0, "day": 86400.0, "d": 86400.0,
}
TIME_NAMES = ("time", "timestamp", "datetime", "date", "elapsed", "epoch")


def error(reason: str, detail: str, code: int = 2) -> None:
    print(json.dumps({"status": "error", "reason": reason, "detail": detail}))
    raise SystemExit(code)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def parse_datetime(text: str) -> float | None:
    try:
        value = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.timestamp()
    except ValueError:
        try:
            return dt.date.fromisoformat(text).toordinal() * 86400.0
        except ValueError:
            return None


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if path.suffix.lower() not in {".csv", ".tsv", ".txt"}:
        error("unsupported_format", "Sampling diagnostics currently accept CSV/TSV text files.")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        try:
            dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            error("missing_header", "No header row found.")
        return list(reader.fieldnames), list(reader)


def infer_time(headers: list[str]) -> str | None:
    lowered = {header.lower(): header for header in headers}
    for candidate in TIME_NAMES:
        if candidate in lowered:
            return lowered[candidate]
    for header in headers:
        lower = header.lower()
        if any(lower.startswith(name + "_") or lower.endswith("_" + name) for name in TIME_NAMES):
            return header
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--time-column")
    parser.add_argument("--time-unit")
    parser.add_argument("--regularity-tolerance", type=float, default=0.05)
    parser.add_argument("--gap-factor", type=float, default=5.0)
    args = parser.parse_args()

    if not args.input.is_file():
        error("file_not_found", str(args.input))
    headers, rows = load_rows(args.input)
    column = args.time_column or infer_time(headers)
    if not column or column not in headers:
        error("column_not_found", "Specify --time-column.")

    raw = [(row.get(column) or "").strip() for row in rows]
    numeric: list[float] = []
    numeric_ok = True
    for text in raw:
        try:
            value = float(text)
            if not math.isfinite(value):
                raise ValueError
            numeric.append(value)
        except ValueError:
            numeric_ok = False
            break

    unit_known = False
    time_kind = "numeric"
    if numeric_ok:
        if args.time_unit:
            unit = args.time_unit.strip().replace("μ", "µ").lower()
            if unit not in TIME_FACTORS:
                error("unsupported_time_unit", args.time_unit)
            times = [value * TIME_FACTORS[unit] for value in numeric]
            unit_known = True
        else:
            times = numeric
    else:
        parsed = [parse_datetime(text) for text in raw]
        if any(value is None for value in parsed):
            error("unparseable_timestamps", "Use a numeric column or ISO-8601 timestamps.")
        times = [float(value) for value in parsed if value is not None]
        time_kind = "datetime"
        unit_known = True

    if len(times) < 3:
        error("insufficient_rows", "At least three timestamps are required.")

    differences = [right - left for left, right in zip(times, times[1:])]
    duplicates = sum(value == 0 for value in differences)
    reversals = sum(value < 0 for value in differences)
    positive = [value for value in differences if value > 0]
    if not positive:
        error("invalid_time_order", "No positive timestamp intervals were found.")

    median_dt = statistics.median(positive)
    deviations = [abs(value - median_dt) / median_dt for value in positive]
    p95_relative_jitter = percentile(deviations, 0.95)
    large_gaps = [
        {"after_row": index + 1, "dt": value}
        for index, value in enumerate(differences, start=1)
        if value > args.gap_factor * median_dt
    ]
    regular = (
        reversals == 0
        and duplicates == 0
        and p95_relative_jitter <= args.regularity_tolerance
        and not large_gaps
    )

    rate = 1.0 / median_dt if unit_known and median_dt > 0 else None
    nyquist = rate / 2.0 if rate is not None else None
    recommendations: list[str] = []
    if not unit_known:
        recommendations.append("Confirm the numeric time unit before reporting Hz, seconds, or Nyquist limits.")
    if reversals:
        recommendations.append("Sort by timestamp only after checking that row order has no domain meaning.")
    if duplicates:
        recommendations.append("Resolve duplicate timestamps before spectral analysis.")
    if large_gaps:
        recommendations.append("Model or segment large gaps; do not silently interpolate across them.")
    if regular:
        recommendations.append("Regular sampling supports FFT/Welch after detrending and missing-value checks.")
    else:
        recommendations.append("Avoid plain FFT on raw timestamps; prefer Lomb-Scargle or justify explicit resampling.")

    result = {
        "status": "ok",
        "time_column": column,
        "time_kind": time_kind,
        "time_unit_confirmed": args.time_unit if numeric_ok and args.time_unit else ("s" if time_kind == "datetime" else None),
        "timestamp_count": len(times),
        "duplicate_intervals": duplicates,
        "reversed_intervals": reversals,
        "median_dt_seconds": median_dt if unit_known else None,
        "median_dt_native_units": median_dt if not unit_known else None,
        "p95_relative_jitter": p95_relative_jitter,
        "largest_gap_seconds": max(positive) if unit_known else None,
        "large_gap_count": len(large_gaps),
        "large_gaps_preview": large_gaps[:10],
        "sampling_rate_hz": rate,
        "nyquist_frequency_hz": nyquist,
        "sampling_regular": regular,
        "recommendations": recommendations,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
