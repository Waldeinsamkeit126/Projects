from __future__ import annotations

import hashlib
import html
import json
import os
import statistics
import time
from bisect import bisect_right
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from .local_table_ocr import TinyOCREngine, _atomic_json, _cell_text, table_html
from .table_grid import _runs


@dataclass(frozen=True)
class PageTile:
    index: int
    core: tuple[int, int, int, int]
    crop: tuple[int, int, int, int]


@dataclass(frozen=True)
class Detection:
    left: float
    top: float
    right: float
    bottom: float
    text: str
    score: float

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


def page_tiles(
    width: int,
    height: int,
    core_size: int = 1200,
    margin: int = 100,
) -> list[PageTile]:
    result = []
    index = 0
    for top in range(0, height, core_size):
        bottom = min(height, top + core_size)
        for left in range(0, width, core_size):
            right = min(width, left + core_size)
            result.append(
                PageTile(
                    index=index,
                    core=(left, top, right, bottom),
                    crop=(
                        max(0, left - margin),
                        max(0, top - margin),
                        min(width, right + margin),
                        min(height, bottom + margin),
                    ),
                )
            )
            index += 1
    return result


def _row_groups(detections: Sequence[Detection]) -> list[list[Detection]]:
    if not detections:
        return []
    typical_height = statistics.median(
        max(1.0, item.bottom - item.top) for item in detections
    )
    threshold = max(3.0, typical_height * 0.72)
    groups: list[list[Detection]] = []
    centers: list[float] = []
    for item in sorted(detections, key=lambda value: value.center_y):
        if not groups or abs(item.center_y - centers[-1]) > threshold:
            groups.append([item])
            centers.append(item.center_y)
        else:
            groups[-1].append(item)
            centers[-1] = statistics.median(value.center_y for value in groups[-1])
    return groups


def _select_rows(groups: list[list[Detection]], expected_rows: int) -> list[list[Detection]]:
    if len(groups) < expected_rows:
        raise ValueError(
            f"not enough detected rows: detected={len(groups)}, expected={expected_rows}"
        )
    best: tuple[float, int] | None = None
    for start in range(len(groups) - expected_rows + 1):
        window = groups[start : start + expected_rows]
        centers = [statistics.median(item.center_y for item in group) for group in window]
        gaps = [right - left for left, right in zip(centers, centers[1:])]
        median_gap = statistics.median(gaps) if gaps else 1.0
        irregularity = (
            statistics.mean(abs(gap - median_gap) for gap in gaps)
            / max(median_gap, 1.0)
        )
        largest_gap = max(gaps, default=median_gap) / max(median_gap, 1.0)
        density_bonus = sum(len(group) for group in window) / max(expected_rows, 1)
        score = irregularity + max(0.0, largest_gap - 2.0) - density_bonus * 0.001
        candidate = (score, start)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return groups[best[1] : best[1] + expected_rows]


def _projection_row_centers(image_path: Path) -> list[float]:
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as source:
            width, height = source.size
            scale = min(1.0, 6000 / max(width, 1))
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            gray = source.convert("L")
            if gray.size != target:
                gray = gray.resize(target, Image.Resampling.BOX)
            array = np.asarray(gray)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    mask = array < 220
    analysis_height, analysis_width = mask.shape
    horizontal_rules = np.flatnonzero(mask.sum(axis=1) > analysis_width * 0.40)
    vertical_rules = np.flatnonzero(mask.sum(axis=0) > analysis_height * 0.40)
    for row in horizontal_rules:
        mask[max(0, row - 1) : min(analysis_height, row + 2), :] = False
    for column in vertical_rules:
        mask[:, max(0, column - 1) : min(analysis_width, column + 2)] = False
    active = np.flatnonzero(mask.sum(axis=1) > max(2, analysis_width // 2500))
    runs = _runs(active, max_internal_gap=1)
    if not runs:
        return []
    heights = [bottom - top + 1 for top, bottom in runs]
    typical = statistics.median(heights)
    filtered = [
        (top, bottom)
        for top, bottom in runs
        if typical * 0.45 <= bottom - top + 1 <= typical * 2.2
    ]
    return [((top + bottom) / 2) / scale for top, bottom in filtered]


def _select_projection_rows(centers: list[float], expected_rows: int) -> list[float]:
    if len(centers) < expected_rows:
        raise ValueError(
            f"not enough projected rows: detected={len(centers)}, expected={expected_rows}"
        )
    best: tuple[float, int] | None = None
    for start in range(len(centers) - expected_rows + 1):
        window = centers[start : start + expected_rows]
        gaps = [right - left for left, right in zip(window, window[1:])]
        median_gap = statistics.median(gaps) if gaps else 1.0
        irregularity = statistics.mean(
            abs(gap - median_gap) for gap in gaps
        ) / max(median_gap, 1.0)
        largest_gap = max(gaps, default=median_gap) / max(median_gap, 1.0)
        candidate = (irregularity + max(0.0, largest_gap - 2.0), start)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return centers[best[1] : best[1] + expected_rows]


def _thin_line_centers(
    active: np.ndarray, maximum_thickness: int = 12
) -> list[float]:
    return [
        (start + end) / 2
        for start, end in _runs(active, max_internal_gap=1)
        if end - start + 1 <= maximum_thickness
    ]


def _line_groups(centers: list[float]) -> list[list[float]]:
    if len(centers) < 3:
        return []
    gaps = np.diff(np.asarray(centers, dtype=np.float32))
    lower = gaps[gaps <= np.percentile(gaps, 60)]
    typical = float(np.median(lower)) if lower.size else float(np.median(gaps))
    split_gap = max(18.0, typical * 4.5)
    groups: list[list[float]] = [[centers[0]]]
    for center in centers[1:]:
        if center - groups[-1][-1] > split_gap:
            groups.append([center])
        else:
            groups[-1].append(center)
    return [group for group in groups if len(group) >= 3]


def _rule_grid_boundaries(
    image_path: Path,
    expected_rows: int,
    expected_columns: int,
    max_width: int = 3000,
    darkness: int = 200,
    horizontal_coverage: float = 0.35,
    vertical_coverage: float = 0.70,
    header_vertical_rules: bool = False,
    header_vertical_coverage: float = 0.50,
) -> tuple[list[float], list[float]]:
    """Return cell boundary rules only when the image proves the exact grid."""

    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as source:
            width, height = source.size
            scale = min(1.0, max_width / max(width, 1))
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            gray = source.convert("L")
            if gray.size != target:
                gray = gray.resize(target, Image.Resampling.BOX)
            array = np.asarray(gray)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit

    mask = array < darkness
    analysis_height, analysis_width = mask.shape
    ink_columns = np.flatnonzero(
        mask.sum(axis=0) > max(3, analysis_height // 2500)
    )
    if ink_columns.size:
        content_left = int(ink_columns[0])
        content_right = int(ink_columns[-1]) + 1
    else:
        content_left, content_right = 0, analysis_width
    content_width = max(1, content_right - content_left)
    horizontal_active = np.flatnonzero(
        mask[:, content_left:content_right].sum(axis=1)
        >= content_width * horizontal_coverage
    )
    horizontal_centers = _thin_line_centers(horizontal_active)
    matching_groups = [
        group
        for group in _line_groups(horizontal_centers)
        if len(group) == expected_rows + 1
    ]
    if len(matching_groups) != 1:
        raise ValueError(
            "image does not prove a unique horizontal rule grid: "
            f"expected={expected_rows + 1}, "
            f"groups={[len(group) for group in _line_groups(horizontal_centers)]}"
        )
    horizontal = matching_groups[0]
    vertical: list[float] = []
    vertical_scale = scale
    if header_vertical_rules:
        # Triangular actuarial tables contain many intentionally blank cells, so
        # full-height coverage can hide real column rules.  Their second header
        # row crosses every year column and therefore proves the complete grid.
        raw_top = max(0, round(horizontal[1] / scale) + 2)
        raw_bottom = min(height, round(horizontal[2] / scale) - 1)
        if raw_bottom <= raw_top:
            raise ValueError("second header row is too narrow for vertical rules")
        old_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            with Image.open(image_path) as source:
                header = np.asarray(
                    source.crop((0, raw_top, width, raw_bottom)).convert("L")
                )
        finally:
            Image.MAX_IMAGE_PIXELS = old_limit
        header_mask = header < darkness
        vertical_active = np.flatnonzero(
            header_mask.sum(axis=0)
            >= header.shape[0] * header_vertical_coverage
        )
        vertical = _thin_line_centers(vertical_active, maximum_thickness=8)
        if len(vertical) == expected_columns + 1:
            vertical_scale = 1.0
    if len(vertical) != expected_columns + 1:
        # Short training headers can make text strokes resemble rules.  Fall
        # back to full-grid evidence instead of accepting an inferred subset.
        top = max(0, round(horizontal[0]))
        bottom = min(analysis_height, round(horizontal[-1]) + 1)
        region_height = max(1, bottom - top)
        vertical_active = np.flatnonzero(
            mask[top:bottom, :].sum(axis=0) >= region_height * vertical_coverage
        )
        vertical = _thin_line_centers(vertical_active)
        vertical_scale = scale
    if len(vertical) != expected_columns + 1:
        raise ValueError(
            "image does not prove the expected vertical rule grid: "
            f"expected={expected_columns + 1}, detected={len(vertical)}"
        )
    return (
        [value / scale for value in horizontal],
        [value / vertical_scale for value in vertical],
    )


def _column_centers(rows: list[list[Detection]], expected_columns: int) -> list[float]:
    exact = [row for row in rows if len(row) == expected_columns]
    if exact:
        selected = max(exact, key=lambda row: sum(item.score for item in row))
        return sorted(item.center_x for item in selected)

    candidates = sorted(
        rows,
        key=lambda row: (abs(len(row) - expected_columns), -len(row)),
    )
    seed = sorted(item.center_x for item in candidates[0])
    if len(seed) >= expected_columns:
        # Preserve the full span while reducing occasional split tokens.
        centers = [
            seed[round(index * (len(seed) - 1) / max(expected_columns - 1, 1))]
            for index in range(expected_columns)
        ]
    else:
        values = sorted(item.center_x for row in rows for item in row)
        if len(values) < expected_columns:
            raise ValueError(
                f"not enough column observations: {len(values)} < {expected_columns}"
            )
        lower, upper = values[0], values[-1]
        centers = [
            lower + (upper - lower) * index / max(expected_columns - 1, 1)
            for index in range(expected_columns)
        ]

    for _ in range(12):
        buckets: list[list[float]] = [[] for _ in centers]
        for row in rows:
            for item in row:
                index = min(
                    range(len(centers)),
                    key=lambda value: abs(item.center_x - centers[value]),
                )
                buckets[index].append(item.center_x)
        updated = [
            statistics.median(bucket) if bucket else center
            for center, bucket in zip(centers, buckets)
        ]
        if max(abs(a - b) for a, b in zip(centers, updated)) < 0.1:
            break
        centers = updated
    return centers


def detect_page_text(
    image_path: Path,
    cache_dir: Path,
    model_root: Path,
    cpu_threads: int = 4,
    recognition_model_name: str = "PP-OCRv6_tiny_rec",
    recognition_model_dir: Path | None = None,
) -> tuple[list[Detection], dict[str, int]]:
    engine: TinyOCREngine | None = None
    detections: list[Detection] = []
    cache_hits = 0
    tiles_run = 0
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as source:
            source = source.convert("RGB")
            for tile in page_tiles(*source.size):
                crop = source.crop(tile.crop)
                if crop.convert("L").getextrema()[0] >= 248:
                    continue
                digest = hashlib.sha256()
                digest.update(b"PP-OCRv6-page-grid-v2\0")
                digest.update(recognition_model_name.encode("utf-8"))
                digest.update(b"\0")
                digest.update(json.dumps(asdict(tile), sort_keys=True).encode("ascii"))
                digest.update(crop.tobytes())
                item_dir = cache_dir / "page_ocr" / digest.hexdigest()
                image_cache = item_dir / "tile.jpg"
                result_cache = item_dir / "result.json"
                if result_cache.is_file():
                    data = json.loads(result_cache.read_text(encoding="utf-8"))
                    cache_hits += 1
                else:
                    item_dir.mkdir(parents=True, exist_ok=True)
                    temporary = image_cache.with_suffix(".jpg.tmp")
                    crop.save(
                        temporary,
                        format="JPEG",
                        quality=95,
                        subsampling=0,
                        optimize=True,
                    )
                    os.replace(temporary, image_cache)
                    if engine is None:
                        engine = TinyOCREngine(
                            model_root,
                            cpu_threads,
                            recognition_model_name=recognition_model_name,
                            recognition_model_dir=recognition_model_dir,
                        )
                    raw = engine.predict(image_cache)
                    data = {
                        "boxes": raw.get("rec_boxes", []),
                        "texts": raw.get("rec_texts", []),
                        "scores": raw.get("rec_scores", []),
                    }
                    _atomic_json(result_cache, data)
                tiles_run += 1
                crop_left, crop_top, _, _ = tile.crop
                core_left, core_top, core_right, core_bottom = tile.core
                for box, text, score in zip(
                    data.get("boxes", []),
                    data.get("texts", []),
                    data.get("scores", []),
                ):
                    if len(box) != 4 or not str(text).strip():
                        continue
                    left, top, right, bottom = (float(value) for value in box)
                    global_box = Detection(
                        left + crop_left,
                        top + crop_top,
                        right + crop_left,
                        bottom + crop_top,
                        str(text),
                        float(score),
                    )
                    if (
                        core_left <= global_box.center_x < core_right
                        and core_top <= global_box.center_y < core_bottom
                    ):
                        detections.append(global_box)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    return detections, {
        "tiles": tiles_run,
        "cache_hits": cache_hits,
        "detections": len(detections),
    }


def constrained_table_ocr(
    image_path: Path,
    expected_rows: int,
    expected_columns: int,
    cache_dir: Path,
    model_root: Path,
    cpu_threads: int = 4,
    expected_row_lengths: Sequence[int] | None = None,
    corner_header_span: bool = False,
    corner_header_columns: int | None = None,
    use_rule_grid: bool = False,
    header_vertical_rules: bool = False,
    rule_grid_max_width: int = 3000,
    rule_grid_horizontal_coverage: float = 0.35,
    rule_grid_header_vertical_coverage: float = 0.50,
    rule_grid_strict_bounds: bool = False,
    recognition_model_name: str = "PP-OCRv6_tiny_rec",
    recognition_model_dir: Path | None = None,
) -> tuple[str, dict[str, object]]:
    if header_vertical_rules and not use_rule_grid:
        raise ValueError("header vertical rules require use_rule_grid")
    if rule_grid_strict_bounds and not use_rule_grid:
        raise ValueError("strict rule grid bounds require use_rule_grid")
    if rule_grid_max_width < 500:
        raise ValueError("rule_grid_max_width must be at least 500")
    if not 0 < rule_grid_horizontal_coverage <= 1:
        raise ValueError("rule grid horizontal coverage must be in (0, 1]")
    if not 0 < rule_grid_header_vertical_coverage <= 1:
        raise ValueError("header vertical coverage must be in (0, 1]")
    if corner_header_span:
        if corner_header_columns not in (None, 1):
            raise ValueError(
                "corner_header_span is the one-column shorthand and conflicts "
                "with corner_header_columns"
            )
        corner_header_columns = 1
    header_columns = int(corner_header_columns or 0)
    if header_columns:
        if expected_row_lengths is not None:
            raise ValueError(
                "corner header columns and expected_row_lengths are mutually exclusive"
            )
        if expected_rows < 2 or not 1 <= header_columns < expected_columns:
            raise ValueError(
                "corner header columns require at least two rows and must be "
                "between one and expected_columns - 1"
            )
        expected_row_lengths = (
            header_columns + 1,
            expected_columns - header_columns,
            *([expected_columns] * (expected_rows - 2)),
        )
    if expected_row_lengths is not None:
        if len(expected_row_lengths) != expected_rows:
            raise ValueError(
                "expected_row_lengths must contain one value per expected row"
            )
        if not expected_row_lengths or max(expected_row_lengths) != expected_columns:
            raise ValueError(
                "expected_columns must equal the largest expected row length"
            )
        if any(length < 1 for length in expected_row_lengths):
            raise ValueError("expected row lengths must be positive")
    started = time.perf_counter()
    detections, tile_report = detect_page_text(
        image_path,
        cache_dir,
        model_root,
        cpu_threads,
        recognition_model_name,
        recognition_model_dir,
    )
    all_groups = _row_groups(detections)
    projected = _projection_row_centers(image_path)
    rule_horizontal: list[float] = []
    rule_vertical: list[float] = []
    if use_rule_grid:
        rule_horizontal, rule_vertical = _rule_grid_boundaries(
            image_path,
            expected_rows,
            expected_columns,
            max_width=rule_grid_max_width,
            horizontal_coverage=rule_grid_horizontal_coverage,
            header_vertical_rules=header_vertical_rules,
            header_vertical_coverage=rule_grid_header_vertical_coverage,
        )
        rows = [[] for _ in range(expected_rows)]
        for item in detections:
            index = bisect_right(rule_horizontal, item.center_y) - 1
            if 0 <= index < expected_rows:
                rows[index].append(item)
        columns = [
            (left + right) / 2
            for left, right in zip(rule_vertical, rule_vertical[1:])
        ]
    elif len(projected) >= expected_rows:
        selected_centers = _select_projection_rows(projected, expected_rows)
        rows = [[] for _ in selected_centers]
        typical_gap = statistics.median(
            right - left
            for left, right in zip(selected_centers, selected_centers[1:])
        )
        for item in detections:
            index = min(
                range(len(selected_centers)),
                key=lambda value: abs(item.center_y - selected_centers[value]),
            )
            if abs(item.center_y - selected_centers[index]) <= typical_gap * 0.48:
                rows[index].append(item)
    else:
        rows = _select_rows(all_groups, expected_rows)
    if not use_rule_grid:
        columns = _column_centers(rows, expected_columns)
    cells: list[list[str]] = []
    for row_index, row in enumerate(rows):
        row_columns = (
            expected_row_lengths[row_index]
            if expected_row_lengths is not None
            else expected_columns
        )
        if header_columns and row_index == 0:
            assigned: list[list[tuple[float, float, str, float]]] = [
                [] for _ in range(header_columns + 1)
            ]
            for item in row:
                column = min(
                    range(len(columns)),
                    key=lambda index: abs(item.center_x - columns[index]),
                )
                assigned[column if column < header_columns else header_columns].append(
                    (item.top, item.left, item.text, item.score)
                )
            cells.append(
                [
                    _cell_text(pieces, row_index, column_index)
                    for column_index, pieces in enumerate(assigned)
                ]
            )
            continue
        if header_columns and row_index == 1:
            assigned = [[] for _ in columns[header_columns:]]
            for item in row:
                column = min(
                    range(header_columns, len(columns)),
                    key=lambda index: abs(item.center_x - columns[index]),
                )
                assigned[column - header_columns].append(
                    (item.top, item.left, item.text, item.score)
                )
            cells.append(
                [
                    _cell_text(pieces, row_index, column_index + header_columns)
                    for column_index, pieces in enumerate(assigned)
                ]
            )
            continue
        if row_columns == 1 and expected_columns > 1:
            pieces = [
                (item.top, item.left, item.text, item.score) for item in row
            ]
            cells.append([_cell_text(pieces, row_index, 0)])
            continue
        if row_columns != expected_columns:
            raise ValueError(
                "only full-width rows and one-cell merged rows are supported"
            )
        assigned: list[list[tuple[float, float, str, float]]] = [
            [] for _ in columns
        ]
        for item in row:
            if rule_grid_strict_bounds and not (
                rule_vertical[0] <= item.center_x <= rule_vertical[-1]
            ):
                continue
            column = min(
                range(len(columns)),
                key=lambda index: abs(item.center_x - columns[index]),
            )
            assigned[column].append((item.top, item.left, item.text, item.score))
        cells.append(
            [
                _cell_text(pieces, row_index, column_index)
                for column_index, pieces in enumerate(assigned)
            ]
        )
    if expected_row_lengths is None:
        markdown = table_html(cells)
    else:
        lines = ['<table border="1" cellpadding="8" cellspacing="0">']
        for row, row_columns in zip(cells, expected_row_lengths):
            if header_columns and len(lines) == 1:
                leading = "".join(
                    f'<td rowspan="2">{html.escape(value)}</td>'
                    for value in row[:header_columns]
                )
                content = (
                    leading
                    + f'<td colspan="{expected_columns - header_columns}">'
                    f"{html.escape(row[header_columns])}</td>"
                )
            elif row_columns == 1 and expected_columns > 1:
                content = (
                    f'<td colspan="{expected_columns}">{html.escape(row[0])}</td>'
                )
            else:
                content = "".join(
                    f"<td>{html.escape(value)}</td>" for value in row
                )
            lines.append(f"      <tr>{content}</tr>")
        lines.append("    </table>")
        markdown = "\n".join(lines)
    return markdown, {
        **tile_report,
        "detected_row_groups": len(all_groups),
        "projected_row_groups": len(projected),
        "rule_grid_used": use_rule_grid,
        "header_vertical_rules_used": header_vertical_rules,
        "rule_grid_max_width": rule_grid_max_width,
        "rule_grid_horizontal_coverage": rule_grid_horizontal_coverage,
        "rule_grid_header_vertical_coverage": (
            rule_grid_header_vertical_coverage
        ),
        "rule_grid_strict_bounds": rule_grid_strict_bounds,
        "recognition_model_name": recognition_model_name,
        "recognition_model_dir": (
            str(recognition_model_dir) if recognition_model_dir is not None else None
        ),
        "rule_horizontal_lines": len(rule_horizontal),
        "rule_vertical_lines": len(rule_vertical),
        "output_rows": len(rows),
        "output_columns": len(columns),
        "output_row_lengths": [len(row) for row in cells],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
