#!/usr/bin/env python3
"""Inspect tabular time-series data and emit a machine-readable inventory."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
import sys
from pathlib import Path


TIME_NAMES = (
    "time", "timestamp", "datetime", "date", "elapsed", "epoch", "sample_time",
)


def fail(reason: str, detail: str, code: int = 2) -> None:
    print(json.dumps({"status": "error", "reason": reason, "detail": detail}))
    raise SystemExit(code)


def read_table(path: Path) -> tuple[list[str], list[dict[str, object]]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv", ".txt"}:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(8192)
            handle.seek(0)
            if suffix == ".tsv":
                dialect = csv.excel_tab
            else:
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
                except csv.Error:
                    dialect = csv.excel
            reader = csv.DictReader(handle, dialect=dialect)
            if not reader.fieldnames:
                fail("missing_header", "The delimited file has no header.")
            headers = [str(name).strip() for name in reader.fieldnames]
            rows = [{str(k).strip(): v for k, v in row.items()} for row in reader]
            return headers, rows

    if suffix in {".xlsx", ".xls", ".parquet"}:
        try:
            import pandas as pd  # type: ignore
        except ImportError:
            fail(
                "missing_dependency",
                f"Reading {suffix} requires pandas and the appropriate file engine.",
            )
        try:
            frame = pd.read_parquet(path) if suffix == ".parquet" else pd.read_excel(path)
        except Exception as exc:
            fail("read_failed", str(exc))
        headers = [str(column) for column in frame.columns]
        frame.columns = headers
        clean = frame.where(frame.notna(), None)
        return headers, clean.to_dict(orient="records")

    fail("unsupported_format", f"Unsupported extension: {suffix or '<none>'}")


def missing(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"", "na", "n/a", "nan", "null", "none"}


def as_float(value: object) -> float | None:
    if missing(value):
        return None
    try:
        result = float(str(value).strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def as_datetime(value: object) -> float | None:
    if missing(value):
        return None
    text = str(value).strip()
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except ValueError:
        try:
            return dt.date.fromisoformat(text).toordinal() * 86400.0
        except ValueError:
            return None


def parse_time(values: list[object]) -> tuple[list[float | None], str, float]:
    numeric = [as_float(value) for value in values]
    numeric_ratio = sum(value is not None for value in numeric) / max(1, len(values))
    dates = [as_datetime(value) for value in values]
    date_ratio = sum(value is not None for value in dates) / max(1, len(values))
    if date_ratio > numeric_ratio and date_ratio >= 0.8:
        return dates, "datetime", date_ratio
    return numeric, "numeric", numeric_ratio


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def infer_time_column(headers: list[str], rows: list[dict[str, object]]) -> str | None:
    ranked: list[tuple[float, str]] = []
    for header in headers:
        name = header.lower().strip()
        values = [row.get(header) for row in rows[:2000]]
        _, kind, ratio = parse_time(values)
        name_score = 0.0
        for index, candidate in enumerate(TIME_NAMES):
            if name == candidate or name.startswith(candidate + "_") or name.endswith("_" + candidate):
                name_score = 3.0 - index * 0.05
                break
        if ratio >= 0.8:
            ranked.append((name_score + ratio + (0.2 if kind == "datetime" else 0.0), header))
    return max(ranked)[1] if ranked else None


def unit_hint(column: str) -> str | None:
    lower = column.lower()
    suffixes = {
        "_ns": "ns", "_us": "us", "_ms": "ms", "_sec": "s", "_seconds": "s",
        "_min": "min", "_hours": "h", "_hz": "Hz", "_khz": "kHz",
    }
    for suffix, unit in suffixes.items():
        if lower.endswith(suffix):
            return unit
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--time-column")
    parser.add_argument("--signal-column", action="append", default=[])
    args = parser.parse_args()

    if not args.input.is_file():
        fail("file_not_found", str(args.input))

    headers, rows = read_table(args.input)
    time_column = args.time_column or infer_time_column(headers, rows)
    if args.time_column and args.time_column not in headers:
        fail("column_not_found", args.time_column)

    missing_by_column = {
        header: sum(missing(row.get(header)) for row in rows) for header in headers
    }
    numeric_ratio: dict[str, float] = {}
    for header in headers:
        present = [row.get(header) for row in rows if not missing(row.get(header))]
        numeric_ratio[header] = (
            sum(as_float(value) is not None for value in present) / len(present)
            if present else 0.0
        )

    signal_columns = args.signal_column or [
        header for header in headers
        if header != time_column and numeric_ratio[header] >= 0.8
    ]
    unknown_signals = [column for column in signal_columns if column not in headers]
    if unknown_signals:
        fail("column_not_found", ", ".join(unknown_signals))

    time_report: dict[str, object] | None = None
    if time_column:
        parsed, time_kind, parse_ratio = parse_time([row.get(time_column) for row in rows])
        valid_times = [value for value in parsed if value is not None]
        differences = [
            right - left
            for left, right in zip(valid_times, valid_times[1:])
        ]
        positive = [value for value in differences if value > 0]
        time_report = {
            "column": time_column,
            "kind": time_kind,
            "parse_success_ratio": round(parse_ratio, 6),
            "unit_hint_unconfirmed": unit_hint(time_column) if time_kind == "numeric" else "s",
            "duplicate_timestamps": len(valid_times) - len(set(valid_times)),
            "is_strictly_increasing": bool(differences) and all(value > 0 for value in differences),
            "median_dt": statistics.median(positive) if positive else None,
            "p95_dt": percentile(positive, 0.95),
            "span": max(valid_times) - min(valid_times) if len(valid_times) >= 2 else None,
        }

    result = {
        "status": "ok",
        "path": str(args.input),
        "format": args.input.suffix.lower().lstrip("."),
        "row_count": len(rows),
        "columns": headers,
        "missing_by_column": missing_by_column,
        "numeric_ratio_by_column": {key: round(value, 6) for key, value in numeric_ratio.items()},
        "time": time_report,
        "signal_columns": signal_columns,
        "warnings": [],
    }
    if not rows:
        result["warnings"].append("Dataset has no data rows.")
    if time_column is None:
        result["warnings"].append("No reliable time column was identified; specify --time-column.")
    elif time_report and time_report["parse_success_ratio"] < 1.0:
        result["warnings"].append("Some timestamps could not be parsed.")
    if time_report and time_report["unit_hint_unconfirmed"]:
        result["warnings"].append("Any unit inferred from a column suffix is unconfirmed.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
