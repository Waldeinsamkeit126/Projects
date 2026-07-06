#!/usr/bin/env python3
"""Independently check a claimed period or a generated CSV/JSON artifact."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path


TIME_FACTORS = {
    "ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1.0,
    "min": 60.0, "h": 3600.0, "day": 86400.0, "d": 86400.0,
}


def error(reason: str, detail: str, code: int = 2) -> None:
    print(json.dumps({"status": "error", "reason": reason, "detail": detail}))
    raise SystemExit(code)


def read_delimited(path: Path) -> tuple[list[str], list[dict[str, str]]]:
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


def parse_times(values: list[str], unit: str | None) -> tuple[list[float], bool]:
    numeric: list[float] = []
    try:
        for text in values:
            value = float(text)
            if not math.isfinite(value):
                raise ValueError
            numeric.append(value)
    except ValueError:
        parsed = [parse_datetime(text) for text in values]
        if any(value is None for value in parsed):
            error("unparseable_timestamps", "Timestamps must be numeric or ISO-8601.")
        return [float(value) for value in parsed if value is not None], True
    if unit is None:
        return numeric, False
    normalized = unit.strip().replace("μ", "µ").lower()
    if normalized not in TIME_FACTORS:
        error("unsupported_time_unit", unit)
    return [value * TIME_FACTORS[normalized] for value in numeric], True


def sinusoid_score(times: list[float], values: list[float], frequency: float) -> float:
    omega = 2.0 * math.pi * frequency
    centered_y = [value - sum(values) / len(values) for value in values]
    cosines = [math.cos(omega * value) for value in times]
    sines = [math.sin(omega * value) for value in times]
    mean_c = sum(cosines) / len(cosines)
    mean_s = sum(sines) / len(sines)
    c = [value - mean_c for value in cosines]
    s = [value - mean_s for value in sines]
    cc = sum(value * value for value in c)
    ss = sum(value * value for value in s)
    cs = sum(left * right for left, right in zip(c, s))
    yc = sum(left * right for left, right in zip(centered_y, c))
    ys = sum(left * right for left, right in zip(centered_y, s))
    determinant = cc * ss - cs * cs
    total = sum(value * value for value in centered_y)
    if determinant <= 1e-15 or total <= 1e-15:
        return 0.0
    beta_c = (yc * ss - ys * cs) / determinant
    beta_s = (ys * cc - yc * cs) / determinant
    explained = beta_c * yc + beta_s * ys
    return max(0.0, min(1.0, explained / total))


def verify_periodicity(args: argparse.Namespace) -> None:
    if args.input.suffix.lower() not in {".csv", ".tsv", ".txt"}:
        error("unsupported_format", "Periodicity verification accepts CSV/TSV text files.")
    headers, rows = read_delimited(args.input)
    for column in (args.time_column, args.signal_column):
        if column not in headers:
            error("column_not_found", column)

    pairs: list[tuple[str, float]] = []
    skipped = 0
    for row in rows:
        time_text = (row.get(args.time_column) or "").strip()
        signal_text = (row.get(args.signal_column) or "").strip()
        try:
            signal = float(signal_text)
            if not math.isfinite(signal) or not time_text:
                raise ValueError
            pairs.append((time_text, signal))
        except ValueError:
            skipped += 1
    if len(pairs) < 12:
        error("insufficient_data", "At least 12 valid time/signal pairs are required.")

    times, unit_known = parse_times([pair[0] for pair in pairs], args.time_unit)
    if not unit_known:
        error("unknown_time_unit", "Provide --time-unit for numeric timestamps.")
    values = [pair[1] for pair in pairs]
    ordered = sorted(zip(times, values))
    times = [item[0] for item in ordered]
    values = [item[1] for item in ordered]
    span = times[-1] - times[0]
    if span <= 0:
        error("invalid_time_span", "Timestamps do not span a positive interval.")
    positive_dt = [
        right - left for left, right in zip(times, times[1:]) if right > left
    ]
    if not positive_dt:
        error("invalid_sampling", "No positive sampling intervals.")
    median_dt = sorted(positive_dt)[len(positive_dt) // 2]
    nyquist = 1.0 / (2.0 * median_dt)
    claimed_frequency = 1.0 / args.claimed_period

    candidates: list[tuple[float, float]] = []
    for index in range(121):
        factor = 0.85 + 0.30 * index / 120.0
        period = args.claimed_period * factor
        score = sinusoid_score(times, values, 1.0 / period)
        candidates.append((score, period))
    best_score, best_period = max(candidates)
    claimed_score = sinusoid_score(times, values, claimed_frequency)
    relative_error = abs(best_period - args.claimed_period) / args.claimed_period
    cycles = span / args.claimed_period
    sampling_safe = claimed_frequency < nyquist
    passed = (
        relative_error <= args.period_tolerance
        and best_score >= args.min_strength
        and cycles >= args.min_cycles
        and sampling_safe
    )
    result = {
        "status": "pass" if passed else "fail",
        "claim": f"period = {args.claimed_period} s",
        "observed_local_peak_period_s": best_period,
        "relative_error": relative_error,
        "claimed_period_fit_strength": claimed_score,
        "best_local_fit_strength": best_score,
        "cycles_observed": cycles,
        "nyquist_frequency_hz": nyquist,
        "sampling_safe": sampling_safe,
        "valid_pairs": len(pairs),
        "skipped_rows": skipped,
        "criteria": {
            "period_tolerance": args.period_tolerance,
            "min_strength": args.min_strength,
            "min_cycles": args.min_cycles,
        },
        "note": "Local sinusoidal-fit validation is supporting evidence, not proof of stationarity or causation.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def verify_output(args: argparse.Namespace) -> None:
    suffix = args.input.suffix.lower()
    expected = [item.strip() for item in (args.expected_columns or "").split(",") if item.strip()]
    if suffix in {".csv", ".tsv", ".txt"}:
        headers, rows = read_delimited(args.input)
        missing_columns = [column for column in expected if column not in headers]
        nonempty = {
            header: sum((row.get(header) or "").strip().lower() not in {"", "na", "n/a", "nan", "null", "none"} for row in rows)
            for header in headers
        }
        all_missing_columns = [column for column, count in nonempty.items() if count == 0]
        passed = len(rows) >= args.min_rows and not missing_columns and not all_missing_columns
        result = {
            "status": "pass" if passed else "fail",
            "type": "delimited",
            "parseable": True,
            "columns": headers,
            "row_count": len(rows),
            "missing_expected_columns": missing_columns,
            "all_missing_columns": all_missing_columns,
        }
    elif suffix == ".json":
        try:
            data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            error("invalid_json", str(exc))
        keys = list(data.keys()) if isinstance(data, dict) else None
        missing_columns = [column for column in expected if keys is None or column not in keys]
        length = len(data) if isinstance(data, list) else 1
        passed = length >= args.min_rows and not missing_columns
        result = {
            "status": "pass" if passed else "fail",
            "type": "json",
            "parseable": True,
            "top_level_type": type(data).__name__,
            "top_level_keys": keys,
            "item_count": length,
            "missing_expected_keys": missing_columns,
        }
    else:
        error("unsupported_format", "Output verification accepts CSV, TSV, or JSON.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    periodicity = subparsers.add_parser("periodicity")
    periodicity.add_argument("input", type=Path)
    periodicity.add_argument("--time-column", required=True)
    periodicity.add_argument("--signal-column", required=True)
    periodicity.add_argument("--time-unit")
    periodicity.add_argument("--claimed-period", type=float, required=True)
    periodicity.add_argument("--period-tolerance", type=float, default=0.05)
    periodicity.add_argument("--min-strength", type=float, default=0.10)
    periodicity.add_argument("--min-cycles", type=float, default=3.0)

    output = subparsers.add_parser("output")
    output.add_argument("input", type=Path)
    output.add_argument("--expected-columns")
    output.add_argument("--min-rows", type=int, default=1)

    args = parser.parse_args()
    if not args.input.is_file():
        error("file_not_found", str(args.input))
    if args.mode == "periodicity":
        if args.claimed_period <= 0:
            error("invalid_period", "--claimed-period must be positive.")
        verify_periodicity(args)
    else:
        verify_output(args)


if __name__ == "__main__":
    main()
