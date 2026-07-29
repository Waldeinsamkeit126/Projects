from __future__ import annotations

import re


FENCE_START = re.compile(r"^\s*```(?:markdown|md|html)?\s*(?:\r?\n)?", re.IGNORECASE)
FENCE_END = re.compile(r"(?:\r?\n)?```\s*$", re.IGNORECASE)


def strip_outer_fence(text: str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    value = FENCE_START.sub("", value, count=1)
    value = FENCE_END.sub("", value, count=1)
    return value.strip()


def conservative_normalize(text: str) -> str:
    """Remove transport artifacts without inventing document content."""
    value = strip_outer_fence(text)
    value = "\n".join(line.rstrip() for line in value.splitlines())
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    return value.strip()


def normalized_for_alignment(text: str) -> str:
    value = conservative_normalize(text)
    return re.sub(r"\s+", "", value)
