from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .data import DatasetLayout
from .image_plan import image_info, vertical_crop_plan
from .local_table_ocr import (
    LOCAL_MAX_TILE_PIXELS,
    LOCAL_MIN_GRID_CELLS,
    local_layout_stats,
    prefer_content_relative_layout,
)
from .table_grid import analyze_table_layout


@dataclass(frozen=True)
class BatchPlanSummary:
    image_count: int
    api_whole_images: int
    api_vertical_images: int
    api_call_estimate: int
    local_table_images: int
    local_table_tiles: int
    local_region_count: int

    def to_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _is_table(path: Path) -> bool:
    return any("table" in part.lower() for part in path.parts)


def build_batch_plan(settings: Settings) -> dict[str, object]:
    dataset = DatasetLayout.discover(settings.data_root)
    records: list[dict[str, object]] = []
    api_whole_images = 0
    api_vertical_images = 0
    api_calls = 0
    local_table_images = 0
    local_table_tiles = 0
    local_region_count = 0

    for image in dataset.test_images:
        info = image_info(image)
        record: dict[str, object] = {
            "file_name": image.name,
            "path": str(image),
            "width": info.width,
            "height": info.height,
            "pixels": info.pixels,
        }
        if _is_table(image) and info.pixels > settings.whole_image_max_pixels:
            page_layout = analyze_table_layout(image, content_relative_rules=False)
            page_stats = local_layout_stats(page_layout)
            layout = page_layout
            stats = page_stats
            rule_scope = "page"
            if not page_stats["suitable"]:
                content_layout = analyze_table_layout(
                    image, content_relative_rules=True
                )
                content_stats = local_layout_stats(content_layout)
                if prefer_content_relative_layout(page_stats, content_stats):
                    layout = content_layout
                    stats = content_stats
                    rule_scope = "content"
            if stats["suitable"]:
                record.update(
                    {
                        "strategy": "local_tiny_ocr_table",
                        "table_rule_scope": rule_scope,
                        "region_count": len(layout.regions),
                        "local_tile_count": stats["tile_count"],
                        "grid_cell_count": stats["total_cells"],
                        "max_local_tile_pixels": stats["max_tile_pixels"],
                    }
                )
                local_table_images += 1
                local_table_tiles += int(stats["tile_count"])
                local_region_count += len(layout.regions)
            else:
                fallback = "api_downscaled_grid_fallback"
                downscale_max_pixels = (
                    settings.crop_max_pixels
                    if info.pixels > 60_000_000
                    else settings.whole_image_max_pixels
                )
                record.update(
                    {
                        "strategy": fallback,
                        "api_calls": 1,
                        "reason": "grid_quality_gate",
                        "region_count": len(layout.regions),
                        "grid_cell_count": stats["total_cells"],
                        "max_local_tile_pixels": stats["max_tile_pixels"],
                        "page_grid_stats": page_stats,
                        "downscale_max_pixels": downscale_max_pixels,
                    }
                )
                api_whole_images += 1
                api_calls += 1
        elif not _is_table(image) and info.pixels > 60_000_000:
            crops = vertical_crop_plan(
                info,
                settings.crop_max_pixels,
                settings.crop_overlap_pixels,
            )
            record.update(
                {
                    "strategy": "api_vertical_overlap",
                    "api_calls": len(crops),
                    "crops": [crop.__dict__ for crop in crops],
                }
            )
            api_vertical_images += 1
            api_calls += len(crops)
        else:
            record.update({"strategy": "api_whole", "api_calls": 1})
            api_whole_images += 1
            api_calls += 1
        records.append(record)

    summary = BatchPlanSummary(
        image_count=len(records),
        api_whole_images=api_whole_images,
        api_vertical_images=api_vertical_images,
        api_call_estimate=api_calls,
        local_table_images=local_table_images,
        local_table_tiles=local_table_tiles,
        local_region_count=local_region_count,
    )
    return {
        "plan_version": 3,
        "routing": {
            "whole_image_max_pixels": settings.whole_image_max_pixels,
            "long_crop_max_pixels": settings.crop_max_pixels,
            "long_crop_overlap_pixels": settings.crop_overlap_pixels,
            "local_min_grid_cells": LOCAL_MIN_GRID_CELLS,
            "local_max_tile_pixels": LOCAL_MAX_TILE_PIXELS,
        },
        "summary": summary.to_dict(),
        "images": records,
    }
