from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.merge import merge_adjacent  # noqa: E402
from afac2026.api import _cache_key, _legacy_cache_key  # noqa: E402
from afac2026.batch_run import _completed_prediction, _write_prediction_meta  # noqa: E402
from afac2026.local_table_ocr import (  # noqa: E402
    adaptive_core_tiles,
    assign_detections,
    core_tile_box,
    core_tiles,
    prefer_content_relative_layout,
    table_html,
)
from afac2026.table_grid import TableLayout  # noqa: E402
from afac2026.normalize import conservative_normalize  # noqa: E402
from afac2026.score import diagnose, levenshtein  # noqa: E402
from afac2026.table_merge import normalize_tile  # noqa: E402
from afac2026.table_grid import TableRegion  # noqa: E402
from afac2026.table_grid import _best_tile_shape  # noqa: E402
from afac2026.table_tiles import TableTileSpec  # noqa: E402
from afac2026.constrained_table_ocr import constrained_table_ocr  # noqa: E402,F401


def slow_levenshtein(left: str, right: str) -> int:
    row = list(range(len(right) + 1))
    for i, x in enumerate(left, 1):
        next_row = [i]
        for j, y in enumerate(right, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = next_row
    return row[-1]


class CoreTests(unittest.TestCase):
    @staticmethod
    def sample_region() -> TableRegion:
        return TableRegion(
            index=0,
            top=0,
            bottom=50,
            header_top=5,
            header_bottom=10,
            row_count_estimate=4,
            column_count_estimate=5,
            row_chunk_size=2,
            column_chunk_size=3,
            tile_count_estimate=4,
            row_intervals=((5, 10), (15, 20), (25, 30), (35, 40)),
            column_intervals=((5, 10), (15, 20), (25, 30), (35, 40), (45, 50)),
        )

    def test_bit_vector_levenshtein_matches_dynamic_programming(self) -> None:
        rng = random.Random(20260712)
        for _ in range(1000):
            left = "".join(rng.choice("abcde") for _ in range(rng.randrange(16)))
            right = "".join(rng.choice("abcde") for _ in range(rng.randrange(16)))
            self.assertEqual(levenshtein(left, right), slow_levenshtein(left, right))

    def test_outer_fence_is_removed(self) -> None:
        self.assertEqual(conservative_normalize("```markdown\r\n# title\r\n```"), "# title")

    def test_adjacent_overlap_is_removed_once(self) -> None:
        self.assertEqual(
            merge_adjacent("alpha\nbeta", "beta\ngamma"),
            "alpha\nbeta\ngamma",
        )

    def test_table_cells_can_match_when_header_tags_differ(self) -> None:
        pred = "<table><tr><td>A</td><td>B</td></tr></table>"
        gt = "<table><tr><th>A</th><th>B</th></tr></table>"
        result = diagnose(pred, gt)
        self.assertTrue(result.table_grid_shape_exact)
        self.assertTrue(result.table_cell_text_exact)
        self.assertFalse(result.table_structure_exact)

    def test_constrained_row_lengths_are_validated_before_ocr(self) -> None:
        with self.assertRaisesRegex(ValueError, "one value per expected row"):
            constrained_table_ocr(
                Path("missing.jpg"),
                3,
                4,
                Path("cache"),
                Path("models"),
                expected_row_lengths=[1, 4],
            )
        with self.assertRaisesRegex(ValueError, "largest expected row length"):
            constrained_table_ocr(
                Path("missing.jpg"),
                3,
                4,
                Path("cache"),
                Path("models"),
                expected_row_lengths=[1, 3, 3],
            )
        with self.assertRaisesRegex(ValueError, "at least two rows"):
            constrained_table_ocr(
                Path("missing.jpg"),
                1,
                4,
                Path("cache"),
                Path("models"),
                corner_header_span=True,
            )
        with self.assertRaisesRegex(ValueError, "between one"):
            constrained_table_ocr(
                Path("missing.jpg"),
                3,
                4,
                Path("cache"),
                Path("models"),
                corner_header_columns=4,
            )
        with self.assertRaisesRegex(ValueError, "require use_rule_grid"):
            constrained_table_ocr(
                Path("missing.jpg"),
                3,
                4,
                Path("cache"),
                Path("models"),
                header_vertical_rules=True,
            )
        with self.assertRaisesRegex(ValueError, "at least 500"):
            constrained_table_ocr(
                Path("missing.jpg"),
                3,
                4,
                Path("cache"),
                Path("models"),
                rule_grid_max_width=100,
            )
    def test_split_corner_header_and_edge_cell_are_normalized(self) -> None:
        markdown = """prefix
<table>
<tr><td>row</td><td>column</td></tr>
<tr><td>1</td><td>2</td></tr>
<tr><td>A</td><td>10</td><td>20</td><td>edge</td></tr>
</table>"""
        spec = TableTileSpec(0, 0, 0, 1, 2, 1, 3)
        result = normalize_tile(markdown, spec)
        self.assertEqual(
            result.grid,
            (("row\\column", "1", "2"), ("A", "10", "20")),
        )
        self.assertEqual(result.discarded_cells, 1)
        self.assertEqual(result.padded_cells, 0)

    def test_local_tiles_cover_each_cell_once_with_overlap_margin(self) -> None:
        region = self.sample_region()
        tiles = core_tiles(region, margin_cells=1)
        covered = [
            (row, column)
            for tile in tiles
            for row in range(tile.row_start, tile.row_end)
            for column in range(tile.column_start, tile.column_end)
        ]
        self.assertEqual(len(covered), 20)
        self.assertEqual(len(set(covered)), 20)
        self.assertEqual(tiles[-1].crop_column_start, 2)
        self.assertEqual(tiles[-1].crop_column_end, 5)

    def test_local_detection_is_assigned_only_to_tile_core(self) -> None:
        region = self.sample_region()
        tile = core_tiles(region, margin_cells=1)[1]
        assigned = assign_detections(
            region,
            tile,
            (15, 0, 50, 30),
            boxes=((19, 14, 21, 16), (11, 14, 14, 16)),
            texts=("core", "margin"),
            scores=(0.99, 0.99),
        )
        self.assertEqual([piece[2] for piece in assigned[(1, 3)]], ["core"])
        self.assertNotIn((1, 2), assigned)

    def test_local_table_html_escapes_cell_text(self) -> None:
        value = table_html((("A&B", "<x>"),))
        self.assertIn("<td>A&amp;B</td>", value)
        self.assertIn("<td>&lt;x&gt;</td>", value)

    def test_tile_shape_supports_fewer_than_five_rows(self) -> None:
        rows, columns, count = _best_tile_shape(2, 100)
        self.assertEqual(rows, 2)
        self.assertGreaterEqual(columns, 3)
        self.assertGreaterEqual(count, 1)

    def test_api_content_cache_is_route_independent(self) -> None:
        image = ROOT / "requirements.txt"
        current = _cache_key(image, "https://example.invalid/api")
        first = _legacy_cache_key(image, "https://example.invalid/api", "route-a")
        second = _legacy_cache_key(image, "https://example.invalid/api", "route-b")
        self.assertNotEqual(first, second)
        self.assertNotIn(current, {first, second})

    def test_local_tile_box_is_bounded_by_layout(self) -> None:
        region = self.sample_region()
        layout = TableLayout("sample", 60, 50, 1.0, 5.0, (region,))
        for tile in core_tiles(region):
            left, top, right, bottom = core_tile_box(layout, region, tile)
            self.assertTrue(0 <= left < right <= layout.width)
            self.assertTrue(region.top <= top < bottom <= region.bottom)

    def test_adaptive_tiles_preserve_cells_under_pixel_budget(self) -> None:
        region = self.sample_region()
        layout = TableLayout("sample", 60, 50, 1.0, 5.0, (region,))
        tiles = adaptive_core_tiles(
            layout, region, margin_cells=0, max_tile_pixels=200
        )
        self.assertGreater(len(tiles), len(core_tiles(region, margin_cells=0)))
        covered = [
            (row, column)
            for tile in tiles
            for row in range(tile.row_start, tile.row_end)
            for column in range(tile.column_start, tile.column_end)
        ]
        self.assertEqual(len(covered), 20)
        self.assertEqual(len(set(covered)), 20)
        for tile in tiles:
            left, top, right, bottom = core_tile_box(layout, region, tile)
            self.assertLessEqual((right - left) * (bottom - top), 200)

    def test_prediction_requires_matching_strategy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "sample.md"
            output.write_text("prediction", encoding="utf-8")
            record = {"file_name": "sample.jpg", "strategy": "api_whole"}
            self.assertIsNone(_completed_prediction(output, record))
            _write_prediction_meta(output, record, "test", "prediction")
            self.assertIsNotNone(_completed_prediction(output, record))
            changed = {**record, "strategy": "local_tiny_ocr_table"}
            self.assertIsNone(_completed_prediction(output, changed))

    def test_api_output_cap_warning_does_not_apply_to_local_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "sample.md"
            markdown = "x" * 11_000
            output.write_text(markdown, encoding="utf-8")
            record = {"file_name": "sample.jpg", "strategy": "api_whole"}
            _write_prediction_meta(output, record, "finixdoc_api", markdown)
            api_meta = _completed_prediction(output, record)
            self.assertIn("near_api_output_cap", api_meta["warnings"])
            _write_prediction_meta(output, record, "ppocrv6_tiny_cpu", markdown)
            local_meta = _completed_prediction(output, record)
            self.assertNotIn("near_api_output_cap", local_meta["warnings"])

    def test_content_layout_requires_material_pixel_improvement(self) -> None:
        page = {
            "suitable": False,
            "max_tile_pixels": 12_000_000,
            "total_cells": 4_000,
            "tile_count": 4,
        }
        content = {
            "suitable": True,
            "max_tile_pixels": 2_000_000,
            "total_cells": 4_500,
            "tile_count": 12,
        }
        self.assertTrue(prefer_content_relative_layout(page, content))
        self.assertFalse(
            prefer_content_relative_layout(
                page, {**content, "max_tile_pixels": 4_000_000}
            )
        )


if __name__ == "__main__":
    unittest.main()
