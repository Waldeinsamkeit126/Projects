from __future__ import annotations

import hashlib
import html
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image

from .table_grid import TableLayout, TableRegion, analyze_table_layout
from .table_tiles import _bounds


LOCAL_MIN_GRID_CELLS = 1_000
LOCAL_MAX_TILE_PIXELS = 3_000_000


@dataclass(frozen=True)
class CoreTile:
    region_index: int
    row_start: int
    row_end: int
    column_start: int
    column_end: int
    crop_row_start: int
    crop_row_end: int
    crop_column_start: int
    crop_column_end: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class LocalTableOCRReport:
    image: str
    output: str
    region_count: int
    tile_count: int
    cache_hits: int
    detections: int
    elapsed_seconds: float
    rule_scope: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def core_tiles(region: TableRegion, margin_cells: int = 1) -> list[CoreTile]:
    result: list[CoreTile] = []
    row_chunk = max(1, region.row_chunk_size)
    column_chunk = max(1, region.column_chunk_size)
    for row_start in range(0, len(region.row_intervals), row_chunk):
        row_end = min(len(region.row_intervals), row_start + row_chunk)
        for column_start in range(0, len(region.column_intervals), column_chunk):
            column_end = min(
                len(region.column_intervals), column_start + column_chunk
            )
            result.append(
                CoreTile(
                    region_index=region.index,
                    row_start=row_start,
                    row_end=row_end,
                    column_start=column_start,
                    column_end=column_end,
                    crop_row_start=max(0, row_start - margin_cells),
                    crop_row_end=min(
                        len(region.row_intervals), row_end + margin_cells
                    ),
                    crop_column_start=max(0, column_start - margin_cells),
                    crop_column_end=min(
                        len(region.column_intervals), column_end + margin_cells
                    ),
                )
            )
    return result


def _render_crop(
    source: Image.Image,
    layout: TableLayout,
    region: TableRegion,
    tile: CoreTile,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    crop_box = core_tile_box(layout, region, tile)
    return source.crop(crop_box).convert("RGB"), crop_box


def core_tile_box(
    layout: TableLayout,
    region: TableRegion,
    tile: CoreTile,
) -> tuple[int, int, int, int]:
    def tight_outer_bounds(
        intervals: tuple[tuple[int, int], ...],
        hard_lower: int,
        hard_upper: int,
    ) -> tuple[int, int]:
        if not intervals:
            return hard_lower, hard_upper
        centers = [(left + right) / 2 for left, right in intervals]
        gaps = [right - left for left, right in zip(centers, centers[1:]) if right > left]
        typical_gap = (
            float(statistics.median(gaps))
            if gaps
            else float(max(4, intervals[0][1] - intervals[0][0]) * 2)
        )
        padding = max(4, round(typical_gap * 0.6))
        return (
            max(hard_lower, intervals[0][0] - padding),
            min(hard_upper, intervals[-1][1] + padding),
        )

    column_lower, column_upper = tight_outer_bounds(
        region.column_intervals, 0, layout.width
    )
    row_lower, row_upper = tight_outer_bounds(
        region.row_intervals, region.top, region.bottom
    )
    x0, x1 = _bounds(
        region.column_intervals,
        tile.crop_column_start,
        tile.crop_column_end,
        column_lower,
        column_upper,
    )
    y0, y1 = _bounds(
        region.row_intervals,
        tile.crop_row_start,
        tile.crop_row_end,
        row_lower,
        row_upper,
    )
    return x0, y0, x1, y1


def _core_tile(
    region: TableRegion,
    row_start: int,
    row_end: int,
    column_start: int,
    column_end: int,
    margin_cells: int,
) -> CoreTile:
    return CoreTile(
        region_index=region.index,
        row_start=row_start,
        row_end=row_end,
        column_start=column_start,
        column_end=column_end,
        crop_row_start=max(0, row_start - margin_cells),
        crop_row_end=min(len(region.row_intervals), row_end + margin_cells),
        crop_column_start=max(0, column_start - margin_cells),
        crop_column_end=min(
            len(region.column_intervals), column_end + margin_cells
        ),
    )


def adaptive_core_tiles(
    layout: TableLayout,
    region: TableRegion,
    margin_cells: int = 1,
    max_tile_pixels: int = LOCAL_MAX_TILE_PIXELS,
) -> list[CoreTile]:
    """Split logical tiles until every crop fits the OCR pixel budget.

    Core ranges remain a disjoint partition; only their one-cell recognition
    margins overlap. This handles scans whose unusually large cells make the
    normal cell-count limit insufficient.
    """

    pending = list(core_tiles(region, margin_cells))
    result: list[CoreTile] = []
    while pending:
        tile = pending.pop()
        left, top, right, bottom = core_tile_box(layout, region, tile)
        pixels = (right - left) * (bottom - top)
        rows = tile.row_end - tile.row_start
        columns = tile.column_end - tile.column_start
        if pixels <= max_tile_pixels or (rows == 1 and columns == 1):
            result.append(tile)
            continue

        candidates: list[list[CoreTile]] = []
        if rows > 1:
            middle = tile.row_start + rows // 2
            candidates.append(
                [
                    _core_tile(
                        region,
                        tile.row_start,
                        middle,
                        tile.column_start,
                        tile.column_end,
                        margin_cells,
                    ),
                    _core_tile(
                        region,
                        middle,
                        tile.row_end,
                        tile.column_start,
                        tile.column_end,
                        margin_cells,
                    ),
                ]
            )
        if columns > 1:
            middle = tile.column_start + columns // 2
            candidates.append(
                [
                    _core_tile(
                        region,
                        tile.row_start,
                        tile.row_end,
                        tile.column_start,
                        middle,
                        margin_cells,
                    ),
                    _core_tile(
                        region,
                        tile.row_start,
                        tile.row_end,
                        middle,
                        tile.column_end,
                        margin_cells,
                    ),
                ]
            )
        if not candidates:
            result.append(tile)
            continue

        def largest_piece(parts: list[CoreTile]) -> int:
            sizes = []
            for part in parts:
                x0, y0, x1, y1 = core_tile_box(layout, region, part)
                sizes.append((x1 - x0) * (y1 - y0))
            return max(sizes)

        pending.extend(min(candidates, key=largest_piece))

    return sorted(
        result,
        key=lambda tile: (
            tile.row_start,
            tile.column_start,
            tile.row_end,
            tile.column_end,
        ),
    )


def local_layout_stats(
    layout: TableLayout,
    margin_cells: int = 1,
    min_grid_cells: int = LOCAL_MIN_GRID_CELLS,
    max_tile_pixels: int = LOCAL_MAX_TILE_PIXELS,
) -> dict[str, int | bool]:
    pairs = [
        (region, tile)
        for region in layout.regions
        for tile in adaptive_core_tiles(
            layout, region, margin_cells, max_tile_pixels
        )
    ]
    total_cells = sum(
        len(region.row_intervals) * len(region.column_intervals)
        for region in layout.regions
    )
    tile_pixels = []
    for region, tile in pairs:
        left, top, right, bottom = core_tile_box(layout, region, tile)
        tile_pixels.append((right - left) * (bottom - top))
    largest_tile_pixels = max(tile_pixels, default=0)
    suitable = (
        bool(layout.regions)
        and bool(pairs)
        and total_cells >= min_grid_cells
        and largest_tile_pixels <= max_tile_pixels
    )
    return {
        "total_cells": total_cells,
        "tile_count": len(pairs),
        "max_tile_pixels": largest_tile_pixels,
        "suitable": suitable,
    }


def prefer_content_relative_layout(
    page_stats: dict[str, int | bool],
    content_stats: dict[str, int | bool],
) -> bool:
    page_max = int(page_stats["max_tile_pixels"])
    content_max = int(content_stats["max_tile_pixels"])
    return (
        not bool(page_stats["suitable"])
        and page_max > LOCAL_MAX_TILE_PIXELS
        and bool(content_stats["suitable"])
        and content_max * 4 <= page_max
        and int(content_stats["total_cells"]) >= int(page_stats["total_cells"])
    )


def _nearest(value: float, centers: Sequence[float]) -> int:
    return min(range(len(centers)), key=lambda index: abs(centers[index] - value))


def assign_detections(
    region: TableRegion,
    tile: CoreTile,
    crop_box: tuple[int, int, int, int],
    boxes: Sequence[Sequence[float]],
    texts: Sequence[str],
    scores: Sequence[float],
) -> dict[tuple[int, int], list[tuple[float, float, str, float]]]:
    x0, y0, _, _ = crop_box
    row_centers = [
        (top + bottom) / 2 - y0
        for top, bottom in region.row_intervals[
            tile.crop_row_start : tile.crop_row_end
        ]
    ]
    column_centers = [
        (left + right) / 2 - x0
        for left, right in region.column_intervals[
            tile.crop_column_start : tile.crop_column_end
        ]
    ]
    assigned: dict[tuple[int, int], list[tuple[float, float, str, float]]] = {}
    for box, text, score in zip(boxes, texts, scores):
        if len(box) != 4 or not row_centers or not column_centers:
            continue
        left, top, right, bottom = (float(value) for value in box)
        local_row = _nearest((top + bottom) / 2, row_centers)
        local_column = _nearest((left + right) / 2, column_centers)
        row = tile.crop_row_start + local_row
        column = tile.crop_column_start + local_column
        if tile.row_start <= row < tile.row_end and tile.column_start <= column < tile.column_end:
            assigned.setdefault((row, column), []).append(
                (top, left, str(text), float(score))
            )
    return assigned


def _cell_text(
    pieces: Iterable[tuple[float, float, str, float]],
    row: int,
    column: int,
) -> str:
    ordered = sorted(pieces)
    values = [piece[2].strip() for piece in ordered if piece[2].strip()]
    if row == 0 and column == 0 and len(values) == 2:
        return "\\".join(values)
    return " ".join(values)


def table_html(cells: Sequence[Sequence[str]]) -> str:
    lines = ['<table border="1" cellpadding="8" cellspacing="0">']
    for row in cells:
        content = "".join(f"<td>{html.escape(value)}</td>" for value in row)
        lines.append(f"      <tr>{content}</tr>")
    lines.append("    </table>")
    return "\n".join(lines)


def _result_json(result: object) -> dict[str, object]:
    value = getattr(result, "json", result)
    if callable(value):
        value = value()
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise TypeError(f"unexpected PaddleOCR result: {type(value)!r}")
    nested = value.get("res")
    return nested if isinstance(nested, dict) else value


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


class TinyOCREngine:
    def __init__(
        self,
        model_root: Path,
        cpu_threads: int = 8,
        recognition_batch_size: int = 64,
        recognition_model_name: str = "PP-OCRv6_tiny_rec",
        recognition_model_dir: Path | None = None,
    ) -> None:
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR

        self.model_root = model_root.resolve()
        recognition_dir = (
            recognition_model_dir.resolve()
            if recognition_model_dir is not None
            else self.model_root / recognition_model_name
        )
        self.engine = PaddleOCR(
            text_detection_model_name="PP-OCRv6_tiny_det",
            text_detection_model_dir=str(self.model_root / "PP-OCRv6_tiny_det"),
            text_recognition_model_name=recognition_model_name,
            text_recognition_model_dir=str(recognition_dir),
            text_recognition_batch_size=recognition_batch_size,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
            enable_mkldnn=False,
            cpu_threads=cpu_threads,
        )

    def predict(self, image_path: Path) -> dict[str, object]:
        results = list(self.engine.predict(str(image_path)))
        if len(results) != 1:
            raise RuntimeError(f"unexpected PaddleOCR result count: {len(results)}")
        return _result_json(results[0])


def ocr_dense_tables(
    image_path: Path,
    output_path: Path,
    cache_dir: Path,
    model_root: Path,
    cpu_threads: int = 8,
    margin_cells: int = 1,
    content_relative_rules: bool = False,
    min_grid_cells: int = LOCAL_MIN_GRID_CELLS,
) -> LocalTableOCRReport:
    started = time.perf_counter()
    layout = analyze_table_layout(
        image_path, content_relative_rules=content_relative_rules
    )
    if not layout.regions:
        raise ValueError("未检测到可重建的高密表格区域")
    all_tiles = [
        tile
        for region in layout.regions
        for tile in adaptive_core_tiles(layout, region, margin_cells)
    ]
    stats = local_layout_stats(
        layout, margin_cells, min_grid_cells=min_grid_cells
    )
    if not stats["suitable"]:
        raise ValueError(
            "网格不适合本地 tiny OCR: "
            f"cells={stats['total_cells']}, "
            f"max_tile_pixels={stats['max_tile_pixels']}"
        )
    engine: TinyOCREngine | None = None
    cache_hits = 0
    detections = 0
    tables: list[str] = []

    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(image_path) as source:
            for region in layout.regions:
                cells = [
                    ["" for _ in region.column_intervals]
                    for _ in region.row_intervals
                ]
                for tile in adaptive_core_tiles(layout, region, margin_cells):
                    crop, crop_box = _render_crop(source, layout, region, tile)
                    digest = hashlib.sha256()
                    digest.update(b"PP-OCRv6-tiny-grid-v1\0")
                    digest.update(json.dumps(tile.to_dict(), sort_keys=True).encode("ascii"))
                    digest.update(crop.tobytes())
                    key = digest.hexdigest()
                    item_dir = cache_dir / "local_ocr" / key
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
                        temporary.replace(image_cache)
                        if engine is None:
                            engine = TinyOCREngine(model_root, cpu_threads)
                        raw = engine.predict(image_cache)
                        data = {
                            "boxes": raw.get("rec_boxes", []),
                            "texts": raw.get("rec_texts", []),
                            "scores": raw.get("rec_scores", []),
                            "crop_box": crop_box,
                            "tile": tile.to_dict(),
                        }
                        _atomic_json(result_cache, data)
                    boxes = data.get("boxes", [])
                    texts = data.get("texts", [])
                    scores = data.get("scores", [])
                    detections += len(texts) if isinstance(texts, list) else 0
                    assigned = assign_detections(
                        region,
                        tile,
                        crop_box,
                        boxes if isinstance(boxes, list) else [],
                        texts if isinstance(texts, list) else [],
                        scores if isinstance(scores, list) else [],
                    )
                    for row in range(tile.row_start, tile.row_end):
                        for column in range(tile.column_start, tile.column_end):
                            cells[row][column] = _cell_text(
                                assigned.get((row, column), []), row, column
                            )
                tables.append(table_html(cells))
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_output.write_text("\n\n".join(tables) + "\n", encoding="utf-8")
    temporary_output.replace(output_path)
    return LocalTableOCRReport(
        image=str(image_path),
        output=str(output_path),
        region_count=len(layout.regions),
        tile_count=len(all_tiles),
        cache_hits=cache_hits,
        detections=detections,
        elapsed_seconds=round(time.perf_counter() - started, 3),
        rule_scope="content" if content_relative_rules else "page",
    )
