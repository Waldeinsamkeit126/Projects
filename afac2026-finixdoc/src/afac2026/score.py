from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser

from .normalize import conservative_normalize


def levenshtein(a: str | list[str], b: str | list[str]) -> int:
    """Exact Levenshtein distance using Python big-integer bit vectors."""
    if len(a) > len(b):
        a, b = b, a
    if not a:
        return len(b)
    masks: dict[object, int] = {}
    for index, item in enumerate(a):
        masks[item] = masks.get(item, 0) | (1 << index)
    highest = 1 << (len(a) - 1)
    positive = ~0
    negative = 0
    score = len(a)
    for item in b:
        equal = masks.get(item, 0)
        xv = equal | negative
        xh = (((equal & positive) + positive) ^ positive) | equal
        ph = negative | ~(xh | positive)
        mh = positive & xh
        if ph & highest:
            score += 1
        elif mh & highest:
            score -= 1
        ph = (ph << 1) | 1
        mh <<= 1
        positive = mh | ~(xv | ph)
        negative = ph & xv
    return score


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables = 0
        self.rows: list[list[tuple[str, str | None, str | None]]] = []
        self.cell_text_rows: list[list[str]] = []
        self._row: list[tuple[str, str | None, str | None]] | None = None
        self._text_row: list[str] | None = None
        self._cell_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = dict(attrs)
        if tag == "table":
            self.tables += 1
        elif tag == "tr":
            self._row = []
            self._text_row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._row.append((tag, attr.get("rowspan"), attr.get("colspan")))
            self._cell_text = []

    def handle_data(self, data: str) -> None:
        if self._cell_text is not None:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell_text is not None and self._text_row is not None:
            self._text_row.append("".join(self._cell_text).strip())
            self._cell_text = None
        elif tag == "tr" and self._row is not None and self._text_row is not None:
            self.rows.append(self._row)
            self.cell_text_rows.append(self._text_row)
            self._row = None
            self._text_row = None


def table_signature(text: str) -> tuple[int, tuple[tuple[tuple[str, str | None, str | None], ...], ...]]:
    parser = _TableParser()
    parser.feed(text)
    return parser.tables, tuple(tuple(row) for row in parser.rows)


def logical_blocks(text: str) -> list[str]:
    value = conservative_normalize(text)
    chunks = re.split(r"\n\s*\n|(?=^#{1,6}\s)|(?=<table\b)|(?<=</table>)", value, flags=re.M | re.I)
    return [re.sub(r"\s+", "", chunk) for chunk in chunks if chunk.strip()]


@dataclass(frozen=True)
class DiagnosticScore:
    text_distance: int
    text_normalized_distance: float
    block_distance: int
    block_normalized_distance: float
    table_count_prediction: int
    table_count_ground_truth: int
    table_structure_exact: bool
    table_grid_shape_exact: bool
    table_cell_text_exact: bool
    table_cell_text_differences: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def diagnose(prediction: str, ground_truth: str) -> DiagnosticScore:
    prediction = conservative_normalize(prediction)
    ground_truth = conservative_normalize(ground_truth)
    text_distance = levenshtein(prediction, ground_truth)
    pred_blocks = logical_blocks(prediction)
    gt_blocks = logical_blocks(ground_truth)
    pred_tables, pred_signature = table_signature(prediction)
    gt_tables, gt_signature = table_signature(ground_truth)
    pred_parser = _TableParser()
    pred_parser.feed(prediction)
    gt_parser = _TableParser()
    gt_parser.feed(ground_truth)
    pred_shape = tuple(tuple(1 for _ in row) for row in pred_parser.rows)
    gt_shape = tuple(tuple(1 for _ in row) for row in gt_parser.rows)
    pred_cells = [cell for row in pred_parser.cell_text_rows for cell in row]
    gt_cells = [cell for row in gt_parser.cell_text_rows for cell in row]
    cell_differences = levenshtein(pred_cells, gt_cells)
    return DiagnosticScore(
        text_distance=text_distance,
        text_normalized_distance=text_distance / max(len(ground_truth), 1),
        block_distance=levenshtein(pred_blocks, gt_blocks),
        block_normalized_distance=levenshtein(pred_blocks, gt_blocks) / max(len(gt_blocks), 1),
        table_count_prediction=pred_tables,
        table_count_ground_truth=gt_tables,
        table_structure_exact=pred_signature == gt_signature,
        table_grid_shape_exact=pred_shape == gt_shape,
        table_cell_text_exact=pred_cells == gt_cells,
        table_cell_text_differences=cell_differences,
    )
