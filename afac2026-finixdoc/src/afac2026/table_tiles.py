from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from .table_grid import TableLayout, TableRegion


@dataclass(frozen=True)
class TableTileSpec:
    region_index: int
    row_group_index: int
    column_group_index: int
    row_start: int
    row_end: int
    column_start: int
    column_end: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def tile_specs(region: TableRegion) -> list[TableTileSpec]:
    data_rows = max(0, len(region.row_intervals) - 1)
    data_columns = max(0, len(region.column_intervals) - 1)
    result: list[TableTileSpec] = []
    for row_group, row_offset in enumerate(range(0, data_rows, region.row_chunk_size)):
        row_start = 1 + row_offset
        row_end = min(len(region.row_intervals), row_start + region.row_chunk_size)
        for column_group, column_offset in enumerate(
            range(0, data_columns, region.column_chunk_size)
        ):
            column_start = 1 + column_offset
            column_end = min(
                len(region.column_intervals),
                column_start + region.column_chunk_size,
            )
            result.append(
                TableTileSpec(
                    region_index=region.index,
                    row_group_index=row_group,
                    column_group_index=column_group,
                    row_start=row_start,
                    row_end=row_end,
                    column_start=column_start,
                    column_end=column_end,
                )
            )
    return result


def all_tile_specs(layout: TableLayout) -> list[TableTileSpec]:
    return [spec for region in layout.regions for spec in tile_specs(region)]


def _bounds(
    intervals: tuple[tuple[int, int], ...],
    start: int,
    end: int,
    lower: int,
    upper: int,
) -> tuple[int, int]:
    if not (0 <= start < end <= len(intervals)):
        raise IndexError((start, end, len(intervals)))
    if start == 0:
        left = lower
    else:
        left = round((intervals[start - 1][1] + intervals[start][0]) / 2)
    if end == len(intervals):
        right = upper
    else:
        right = round((intervals[end - 1][1] + intervals[end][0]) / 2)
    return max(lower, left), min(upper, right)


def _paste_grid(image: Image.Image, x_ranges: list[tuple[int, int]], y_ranges: list[tuple[int, int]]) -> Image.Image:
    widths = [right - left for left, right in x_ranges]
    heights = [bottom - top for top, bottom in y_ranges]
    canvas = Image.new("RGB", (sum(widths), sum(heights)), "white")
    y_out = 0
    for (top, bottom), height in zip(y_ranges, heights):
        x_out = 0
        for (left, right), width in zip(x_ranges, widths):
            piece = image.crop((left, top, right, bottom)).convert("RGB")
            canvas.paste(piece, (x_out, y_out))
            x_out += width
        y_out += height
    return canvas


def render_tile(
    image_path: Path,
    layout: TableLayout,
    spec: TableTileSpec,
    destination: Path,
    jpeg_quality: int = 95,
) -> dict[str, object]:
    region = layout.regions[spec.region_index]
    rows = region.row_intervals
    columns = region.column_intervals
    if len(rows) < 2 or len(columns) < 2:
        raise ValueError("检测到的表格行列不足，拒绝生成无意义切片")

    key_x = _bounds(columns, 0, 1, 0, layout.width)
    data_x = _bounds(columns, spec.column_start, spec.column_end, 0, layout.width)
    if spec.column_start == 1:
        x_ranges = [(key_x[0], data_x[1])]
    else:
        x_ranges = [key_x, data_x]

    header_y = _bounds(rows, 0, 1, region.top, region.bottom)
    data_y = _bounds(rows, spec.row_start, spec.row_end, region.top, region.bottom)
    if spec.row_start == 1:
        # Only the first row/column tile carries the table title/prefix.
        top = region.top if spec.column_start == 1 else header_y[0]
        y_ranges = [(top, data_y[1])]
    else:
        y_ranges = [header_y, data_y]

    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as image:
            tile = _paste_grid(image, x_ranges, y_ranges)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = destination.with_suffix(destination.suffix + ".tmp")
            tile.save(
                temp,
                format="JPEG",
                quality=jpeg_quality,
                subsampling=0,
                optimize=True,
            )
            temp.replace(destination)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    return {
        "destination": str(destination),
        "bytes": destination.stat().st_size,
        "width": tile.width,
        "height": tile.height,
        "spec": spec.to_dict(),
        "x_ranges": x_ranges,
        "y_ranges": y_ranges,
    }
