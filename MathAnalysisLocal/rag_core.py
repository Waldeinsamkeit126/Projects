from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_INDEX = Path(__file__).parent / "index" / "zorich_analysis_i.json"


TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\\[A-Za-z]+|[0-9]+|[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


@dataclass
class SearchHit:
    chunk_id: int
    score: float
    page_start: int
    page_end: int
    text: str

    @property
    def source(self) -> str:
        if self.page_start == self.page_end:
            return f"p. {self.page_start}"
        return f"pp. {self.page_start}-{self.page_end}"


class TextbookIndex:
    def __init__(self, path: Path = DEFAULT_INDEX):
        self.path = path
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        self.meta = payload["meta"]
        self.chunks = payload["chunks"]
        self.doc_freq = payload["doc_freq"]
        self.avgdl = payload["avgdl"]
        self.doc_count = len(self.chunks)

    def search(self, query: str, top_k: int = 6) -> list[SearchHit]:
        terms = tokenize(query)
        if not terms:
            return []
        query_terms = Counter(terms)
        scores: list[tuple[float, dict]] = []
        k1 = 1.5
        b = 0.75
        for chunk in self.chunks:
            tf = chunk["term_freq"]
            dl = chunk["token_count"] or 1
            score = 0.0
            for term, qf in query_terms.items():
                freq = tf.get(term, 0)
                if not freq:
                    continue
                df = self.doc_freq.get(term, 0)
                idf = math.log(1 + (self.doc_count - df + 0.5) / (df + 0.5))
                denom = freq + k1 * (1 - b + b * dl / self.avgdl)
                score += idf * (freq * (k1 + 1) / denom) * min(qf, 3)
            if score > 0:
                scores.append((score, chunk))
        scores.sort(key=lambda pair: pair[0], reverse=True)
        return [
            SearchHit(
                chunk_id=chunk["id"],
                score=score,
                page_start=chunk["page_start"],
                page_end=chunk["page_end"],
                text=chunk["text"],
            )
            for score, chunk in scores[:top_k]
        ]


class LocalLLM:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.1,
    ):
        self.provider = (provider or os.getenv("LOCAL_LLM_PROVIDER") or "ollama").lower()
        self.model = model or os.getenv("LOCAL_LLM_MODEL") or "qwen2.5:7b"
        self.base_url = base_url or os.getenv("LOCAL_LLM_BASE_URL")
        self.temperature = temperature

    def complete(self, messages: list[dict[str, str]]) -> str:
        if self.provider == "ollama":
            return self._ollama_chat(messages)
        if self.provider in {"openai", "lmstudio", "llamacpp", "vllm"}:
            return self._openai_compatible_chat(messages)
        raise ValueError(f"Unsupported LOCAL_LLM_PROVIDER: {self.provider}")

    def _ollama_chat(self, messages: list[dict[str, str]]) -> str:
        url = (self.base_url or "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        data = _post_json(url, payload)
        return data.get("message", {}).get("content", "").strip()

    def _openai_compatible_chat(self, messages: list[dict[str, str]]) -> str:
        url = (self.base_url or "http://127.0.0.1:1234/v1").rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False,
        }
        data = _post_json(url, payload)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot reach local model service at {url}. Start Ollama, LM Studio, or llama.cpp first."
        ) from exc


def build_context(hits: Iterable[SearchHit], max_chars: int = 12000) -> str:
    parts = []
    used = 0
    for i, hit in enumerate(hits, start=1):
        header = f"[Source {i}: {hit.source}, chunk {hit.chunk_id}]"
        body = hit.text.strip()
        piece = f"{header}\n{body}\n"
        if used + len(piece) > max_chars:
            break
        parts.append(piece)
        used += len(piece)
    return "\n".join(parts)


def maybe_rewrite_query(question: str, llm: LocalLLM) -> str:
    prompt = (
        "Rewrite the user's question as concise English mathematical-analysis search keywords. "
        "Keep formulas and named theorems. Return only keywords, no explanation."
    )
    try:
        rewritten = llm.complete(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ]
        )
    except Exception:
        return question
    return f"{question}\n{rewritten}"


def answer_question(question: str, index: TextbookIndex, llm: LocalLLM, top_k: int = 6) -> dict:
    retrieval_query = maybe_rewrite_query(question, llm)
    hits = index.search(retrieval_query, top_k=top_k)
    context = build_context(hits)
    if not hits:
        return {
            "answer": "教材索引中没有检索到足够相关的内容。你可以换用英文关键词、定理名或页码再问一次。",
            "hits": [],
        }

    system = """你是数学分析课程的本地教材助教，只能回答数学分析相关问题。
回答必须严格基于给出的教材片段，不要使用片段之外的事实来补全证明。
如果片段不足以支持完整回答，明确说明“教材片段不足以完全回答”，然后只给出已被片段支持的部分。
回答时优先给出定义、定理条件、证明思路和关键步骤。不要回答与数学分析无关的问题。
每个关键结论后用 [Source n] 标注依据。"""
    user = f"""教材片段：
{context}

问题：
{question}

请用中文回答。"""
    answer = llm.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    return {
        "answer": answer,
        "hits": [
            {
                "source": hit.source,
                "score": round(hit.score, 3),
                "chunk_id": hit.chunk_id,
                "preview": hit.text[:600].strip(),
            }
            for hit in hits
        ],
    }
