from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class TextRow:
    top: int
    bottom: int
    components: int


@dataclass(frozen=True)
class TableRegion:
    index: int
    top: int
    bottom: int
    header_top: int
    header_bottom: int
    row_count_estimate: int
    column_count_estimate: int
    row_chunk_size: int
    column_chunk_size: int
    tile_count_estimate: int
    row_intervals: tuple[tuple[int, int], ...]
    column_intervals: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class TableLayout:
    image: str
    width: int
    height: int
    analysis_scale: float
    median_text_height: float
    regions: tuple[TableRegion, ...]

    @property
    def tile_count_estimate(self) -> int:
        return sum(region.tile_count_estimate for region in self.regions)

    def to_dict(self) -> dict[str, object]:
        return {
            "image": self.image,
            "width": self.width,
            "height": self.height,
            "analysis_scale": self.analysis_scale,
            "median_text_height": self.median_text_height,
            "region_count": len(self.regions),
            "tile_count_estimate": self.tile_count_estimate,
            "regions": [asdict(region) for region in self.regions],
        }


def _runs(active: np.ndarray, max_internal_gap: int = 1) -> list[tuple[int, int]]:
    if active.size == 0:
        return []
    result: list[tuple[int, int]] = []
    start = previous = int(active[0])
    for raw in active[1:]:
        value = int(raw)
        if value - previous > max_internal_gap + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def _component_intervals(
    mask: np.ndarray,
    top: int,
    bottom: int,
    split_gap: int,
) -> list[tuple[int, int]]:
    columns = np.flatnonzero(mask[top : bottom + 1].sum(axis=0) > 0)
    if columns.size == 0:
        return []
    result: list[tuple[int, int]] = []
    start = previous = int(columns[0])
    for raw in columns[1:]:
        value = int(raw)
        if value - previous > split_gap:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def _best_tile_shape(rows: int, columns: int, max_cells: int = 450) -> tuple[int, int, int]:
    """Minimize tile count while keeping repeated headers under output limits."""
    rows = max(rows, 1)
    columns = max(columns, 1)
    best: tuple[int, int, int, int] | None = None
    # Small A-set tables can contain fewer than five data rows.
    for row_chunk in range(min(5, rows), min(rows, 30) + 1):
        # One repeated header row and one repeated row-key column are included.
        column_chunk = max(3, max_cells // (row_chunk + 1) - 1)
        column_chunk = min(column_chunk, columns)
        count = math.ceil(rows / row_chunk) * math.ceil(columns / column_chunk)
        used_cells = (row_chunk + 1) * (column_chunk + 1)
        candidate = (count, -used_cells, row_chunk, column_chunk)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return best[2], best[3], best[0]


def analyze_table_layout(
    path: Path,
    analysis_max_width: int = 6000,
    darkness_threshold: int = 220,
    line_coverage: float = 0.40,
    min_components: int = 5,
    region_gap_factor: float = 2.5,
    content_relative_rules: bool = False,
) -> TableLayout:
    """Detect dense table regions with only deterministic image projections.

    Long horizontal/vertical rules are removed before text-row analysis. This
    is important for bordered financial tables, whose grid lines otherwise
    merge every cell into one connected projection.
    """
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path) as image:
            width, height = image.size
            scale = min(1.0, analysis_max_width / max(width, 1))
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            gray = image.convert("L")
            if gray.size != target:
                gray = gray.resize(target, Image.Resampling.BOX)
            array = np.asarray(gray)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit

    mask = array < darkness_threshold
    analysis_height, analysis_width = mask.shape
    if content_relative_rules:
        # Large white page margins can hide rules that span the whole table but
        # only the upper third of the page. This mode is a guarded fallback;
        # the page-relative behavior remains the stable default.
        ink_rows = np.flatnonzero(
            mask.sum(axis=1) > max(3, analysis_width // 2000)
        )
        ink_columns = np.flatnonzero(
            mask.sum(axis=0) > max(3, analysis_height // 2000)
        )
        if ink_rows.size and ink_columns.size:
            content_top = int(ink_rows[0])
            content_bottom = int(ink_rows[-1]) + 1
            content_left = int(ink_columns[0])
            content_right = int(ink_columns[-1]) + 1
        else:
            content_top, content_bottom = 0, analysis_height
            content_left, content_right = 0, analysis_width
        content_height = max(1, content_bottom - content_top)
        content_width = max(1, content_right - content_left)
        horizontal_rules = np.flatnonzero(
            mask[:, content_left:content_right].sum(axis=1)
            > content_width * line_coverage
        )
        vertical_rules = np.flatnonzero(
            mask[content_top:content_bottom, :].sum(axis=0)
            > content_height * line_coverage
        )
    else:
        horizontal_rules = np.flatnonzero(
            mask.sum(axis=1) > analysis_width * line_coverage
        )
        vertical_rules = np.flatnonzero(
            mask.sum(axis=0) > analysis_height * line_coverage
        )
    for row in horizontal_rules:
        mask[max(0, row - 1) : min(analysis_height, row + 2), :] = False
    for column in vertical_rules:
        mask[:, max(0, column - 1) : min(analysis_width, column + 2)] = False

    active_rows = np.flatnonzero(mask.sum(axis=1) > max(3, analysis_width // 2000))
    row_runs = _runs(active_rows, max_internal_gap=1)
    if not row_runs:
        return TableLayout(str(path), width, height, scale, 0.0, ())
    median_height = float(statistics.median(bottom - top + 1 for top, bottom in row_runs))
    component_gap = max(3, round(median_height * 0.55))
    rows = [
        TextRow(
            top,
            bottom,
            len(_component_intervals(mask, top, bottom, component_gap)),
        )
        for top, bottom in row_runs
    ]

    table_rows = [row for row in rows if row.components >= min_components]
    groups: list[list[TextRow]] = []
    max_gap = max(8.0, median_height * region_gap_factor)
    for row in table_rows:
        if not groups or row.top - groups[-1][-1].bottom > max_gap:
            groups.append([row])
        else:
            groups[-1].append(row)
    groups = [group for group in groups if len(group) >= 2]

    regions: list[TableRegion] = []
    for index, group in enumerate(groups):
        previous_end = groups[index - 1][-1].bottom if index else 0
        next_start = groups[index + 1][0].top if index + 1 < len(groups) else analysis_height
        top = 0 if index == 0 else round((previous_end + group[0].top) / 2)
        bottom = analysis_height if index + 1 == len(groups) else round((group[-1].bottom + next_start) / 2)
        header = max(group, key=lambda row: row.components)
        region_rows = [row for row in group if row.top >= header.top]
        header_columns = _component_intervals(
            mask,
            header.top,
            header.bottom,
            component_gap,
        )
        row_count = max(1, len(region_rows))
        column_count = max(1, len(header_columns))
        data_rows = max(1, row_count - 1)
        data_columns = max(1, column_count - 1)
        row_chunk, column_chunk, tile_count = _best_tile_shape(data_rows, data_columns)

        def original(value: int) -> int:
            return min(height, max(0, round(value / scale)))

        row_intervals = tuple(
            (original(row.top), original(row.bottom + 1))
            for row in region_rows
        )
        column_intervals = tuple(
            (min(width, max(0, round(left / scale))), min(width, max(0, round((right + 1) / scale))))
            for left, right in header_columns
        )

        regions.append(
            TableRegion(
                index=index,
                top=original(top),
                bottom=original(bottom),
                header_top=original(header.top),
                header_bottom=original(header.bottom + 1),
                row_count_estimate=row_count,
                column_count_estimate=column_count,
                row_chunk_size=row_chunk,
                column_chunk_size=column_chunk,
                tile_count_estimate=tile_count,
                row_intervals=row_intervals,
                column_intervals=column_intervals,
            )
        )
    return TableLayout(
        image=str(path),
        width=width,
        height=height,
        analysis_scale=scale,
        median_text_height=median_height / scale,
        regions=tuple(regions),
    )
