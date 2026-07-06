from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from pypdf import PdfReader

from rag_core import DEFAULT_INDEX, tokenize


DEFAULT_PDF = Path(
    r"C:\Users\zhhzh\Documents\WXWork\1688856959714207\Cache\File\2026-03\Vladimir A. Zorich - Mathematical Analysis I-Springer (2016).pdf"
)


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pages(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    pages = []
    for idx, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        if text:
            pages.append({"page": idx, "text": text})
    return pages


def chunk_pages(pages: list[dict], max_tokens: int = 850, overlap: int = 100) -> list[dict]:
    chunks = []
    current: list[str] = []
    current_pages: list[int] = []
    current_tokens: list[str] = []

    def flush() -> None:
        nonlocal current, current_pages, current_tokens
        if not current:
            return
        text = "\n\n".join(current).strip()
        chunks.append(
            {
                "id": len(chunks),
                "page_start": min(current_pages),
                "page_end": max(current_pages),
                "text": text,
            }
        )
        if overlap > 0:
            words = text.split()
            tail = " ".join(words[-overlap:])
            current = [tail] if tail else []
            current_pages = [current_pages[-1]] if current_pages else []
            current_tokens = tokenize(tail)
        else:
            current = []
            current_pages = []
            current_tokens = []

    for page in pages:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page["text"]) if p.strip()]
        for para in paragraphs:
            para_tokens = tokenize(para)
            if current and len(current_tokens) + len(para_tokens) > max_tokens:
                flush()
            current.append(para)
            current_pages.append(page["page"])
            current_tokens.extend(para_tokens)
    flush()
    return chunks


def build_index(pdf_path: Path, output_path: Path) -> None:
    pages = read_pages(pdf_path)
    chunks = chunk_pages(pages)
    doc_freq = defaultdict(int)
    total_len = 0

    for chunk in chunks:
        tokens = tokenize(chunk["text"])
        counts = Counter(tokens)
        chunk["term_freq"] = dict(counts)
        chunk["token_count"] = len(tokens)
        total_len += len(tokens)
        for term in counts:
            doc_freq[term] += 1

    payload = {
        "meta": {
            "title": "Vladimir A. Zorich - Mathematical Analysis I",
            "pdf_path": str(pdf_path),
            "page_count_with_text": len(pages),
            "chunk_count": len(chunks),
        },
        "avgdl": total_len / max(len(chunks), 1),
        "doc_freq": dict(doc_freq),
        "chunks": chunks,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"Indexed {len(pages)} pages into {len(chunks)} chunks.")
    print(f"Saved index to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local searchable index from the Zorich textbook PDF.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_INDEX)
    args = parser.parse_args()
    build_index(args.pdf, args.out)


if __name__ == "__main__":
    main()
