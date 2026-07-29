from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser

from .table_grid import TableRegion
from .table_tiles import TableTileSpec


class _CellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append("\n")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def parse_largest_table(markdown: str) -> tuple[str, list[list[str]], str, bool]:
    lower = markdown.lower()
    start = lower.find("<table")
    end = lower.rfind("</table>")
    closed = start >= 0 and end >= start
    prefix = markdown[:start].strip() if start >= 0 else markdown.strip()
    suffix = markdown[end + len("</table>") :].strip() if closed else ""
    parser = _CellParser()
    parser.feed(markdown)
    if not parser.tables:
        return prefix, [], suffix, closed
    table = max(parser.tables, key=lambda rows: sum(len(row) for row in rows))
    return prefix, table, suffix, closed


@dataclass(frozen=True)
class NormalizedTile:
    prefix: str
    grid: tuple[tuple[str, ...], ...]
    suffix: str
    table_closed: bool
    padded_cells: int
    discarded_cells: int


def _fit(row: list[str], expected: int) -> tuple[list[str], int, int]:
    if len(row) < expected:
        return row + [""] * (expected - len(row)), expected - len(row), 0
    if len(row) > expected:
        return row[:expected], 0, len(row) - expected
    return row, 0, 0


def normalize_tile(markdown: str, spec: TableTileSpec) -> NormalizedTile:
    prefix, rows, suffix, closed = parse_largest_table(markdown)
    data_rows = spec.row_end - spec.row_start
    data_columns = spec.column_end - spec.column_start
    expected_columns = data_columns + 1
    if not rows:
        return NormalizedTile(prefix, (), suffix, closed, 0, 0)

    # FinixDoc sometimes emits the corner labels as a separate two-cell row,
    # followed by the actual column header row. The official GT combines them.
    if (
        len(rows) >= 2
        and 1 <= len(rows[0]) <= 2
        and len(rows[1]) in {data_columns, expected_columns}
    ):
        corner = "\\".join(cell for cell in rows[0] if cell)
        header_tail = rows[1][-data_columns:] if data_columns else []
        header = [corner] + header_tail
        body = rows[2:]
    else:
        header = rows[0]
        body = rows[1:]

    padded = discarded = 0
    fitted: list[list[str]] = []
    header, add, drop = _fit(header, expected_columns)
    padded += add
    discarded += drop
    fitted.append(header)
    for row in body[:data_rows]:
        row, add, drop = _fit(row, expected_columns)
        padded += add
        discarded += drop
        fitted.append(row)
    while len(fitted) < data_rows + 1:
        fitted.append([""] * expected_columns)
        padded += expected_columns
    discarded += max(0, len(body) - data_rows) * expected_columns
    return NormalizedTile(
        prefix=prefix,
        grid=tuple(tuple(row) for row in fitted),
        suffix=suffix,
        table_closed=closed,
        padded_cells=padded,
        discarded_cells=discarded,
    )


class TableAccumulator:
    def __init__(self, region: TableRegion) -> None:
        self.region = region
        self._cells: list[list[list[str]]] = [
            [[] for _ in range(region.column_count_estimate)]
            for _ in range(region.row_count_estimate)
        ]
        self.prefixes: list[str] = []
        self.suffixes: list[str] = []
        self.tile_warnings: list[str] = []

    def _vote(self, row: int, column: int, value: str) -> None:
        if 0 <= row < len(self._cells) and 0 <= column < len(self._cells[row]):
            self._cells[row][column].append(value)

    def add(self, spec: TableTileSpec, tile: NormalizedTile) -> None:
        if not tile.grid:
            self.tile_warnings.append(f"空表格: {spec}")
            return
        if not tile.table_closed:
            self.tile_warnings.append(f"HTML未闭合: {spec}")
        if tile.padded_cells:
            self.tile_warnings.append(f"补空单元格{tile.padded_cells}: {spec}")
        if tile.discarded_cells:
            self.tile_warnings.append(f"丢弃边缘单元格{tile.discarded_cells}: {spec}")
        if spec.row_group_index == 0 and spec.column_group_index == 0 and tile.prefix:
            self.prefixes.append(tile.prefix)
        if tile.suffix:
            self.suffixes.append(tile.suffix)

        self._vote(0, 0, tile.grid[0][0])
        for local_column, global_column in enumerate(
            range(spec.column_start, spec.column_end),
            start=1,
        ):
            self._vote(0, global_column, tile.grid[0][local_column])
        for local_row, global_row in enumerate(range(spec.row_start, spec.row_end), start=1):
            self._vote(global_row, 0, tile.grid[local_row][0])
            for local_column, global_column in enumerate(
                range(spec.column_start, spec.column_end),
                start=1,
            ):
                self._vote(global_row, global_column, tile.grid[local_row][local_column])

    @staticmethod
    def _choose(values: list[str]) -> str:
        if not values:
            return ""
        nonempty = [value for value in values if value]
        candidates = nonempty or values
        counts = Counter(candidates)
        # Counter preserves first-seen order for ties.
        return counts.most_common(1)[0][0]

    def grid(self) -> list[list[str]]:
        return [[self._choose(values) for values in row] for row in self._cells]

    def missing_cells(self) -> int:
        return sum(not values for row in self._cells for values in row)

    def to_html(self) -> str:
        lines = ['<table border="1" cellpadding="8" cellspacing="0">']
        for row in self.grid():
            cells = "".join(f"<td>{escape(value)}</td>" for value in row)
            lines.append(f"      <tr>{cells}</tr>")
        lines.append("    </table>")
        prefix = self.prefixes[0].strip() + "\n\n" if self.prefixes else ""
        suffix = "\n\n" + self.suffixes[0].strip() if self.suffixes else ""
        return prefix + "\n".join(lines) + suffix
