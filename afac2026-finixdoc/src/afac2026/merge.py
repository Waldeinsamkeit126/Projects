from __future__ import annotations

from difflib import SequenceMatcher

from .normalize import conservative_normalize


def _line_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.strip(), right.strip(), autojunk=False).ratio()


def merge_adjacent(left: str, right: str, max_lines: int = 80) -> str:
    """Merge only the boundary of adjacent crops.

    Exact line overlap is preferred. A conservative fuzzy fallback is used only
    when at least two consecutive boundary lines match strongly, preventing
    deletion of legitimate repeated clauses elsewhere in a document.
    """
    a = conservative_normalize(left).splitlines()
    b = conservative_normalize(right).splitlines()
    limit = min(len(a), len(b), max_lines)
    for count in range(limit, 0, -1):
        if a[-count:] == b[:count]:
            return "\n".join(a + b[count:]).strip()
    for count in range(limit, 1, -1):
        pairs = zip(a[-count:], b[:count])
        scores = [_line_similarity(x, y) for x, y in pairs]
        if min(scores) >= 0.94 and sum(scores) / len(scores) >= 0.97:
            return "\n".join(a + b[count:]).strip()
    return "\n".join(a + b).strip()


def merge_many(parts: list[str]) -> str:
    if not parts:
        return ""
    result = parts[0]
    for part in parts[1:]:
        result = merge_adjacent(result, part)
    return conservative_normalize(result)
