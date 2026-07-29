from __future__ import annotations

import hashlib
import http.client
import json
import os
import random
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .normalize import conservative_normalize


@dataclass(frozen=True)
class ApiResult:
    markdown: str
    elapsed_seconds: float
    cache_hit: bool
    cache_key: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_key(image: Path, endpoint: str) -> str:
    # All official whitelist IDs call the same fixed model. Keeping userId out
    # of the content key lets a retry move to another route without paying for
    # the same image twice.
    payload = f"v2\0{endpoint}\0{image.name}\0{_sha256_file(image)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _legacy_cache_key(image: Path, endpoint: str, user_id: str) -> str:
    payload = f"v1\0{endpoint}\0{user_id}\0{image.name}\0{_sha256_file(image)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _multipart(image: Path, user_id: str, api_key: str) -> tuple[bytes, str]:
    boundary = "----afac2026" + uuid.uuid4().hex
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    add_field("userId", user_id)
    add_field("apiKey", api_key)
    add_field("fileName", image.name)
    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{image.name}"\r\n'.encode(),
            b"Content-Type: image/jpeg\r\n\r\n",
            image.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(parts), boundary


def extract_markdown(raw: bytes) -> str:
    outer = json.loads(raw.decode("utf-8"))
    if not outer.get("success"):
        raise RuntimeError(f"FinixDoc API 返回失败: {outer.get('message')!r}")
    nested = outer.get("result", {}).get("result")
    if not isinstance(nested, str):
        raise RuntimeError("FinixDoc API 响应缺少 result.result")
    inner = json.loads(nested)
    choices = inner.get("choices") or []
    if not choices:
        raise RuntimeError("FinixDoc API 响应没有 choices")
    markdown = choices[0].get("message", {}).get("content")
    if not isinstance(markdown, str) or not markdown.strip():
        raise RuntimeError("FinixDoc API 返回空内容")
    return conservative_normalize(markdown)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def call_image(image: Path, settings: Settings, force: bool = False) -> ApiResult:
    key = _cache_key(image, settings.endpoint)
    entry = settings.cache_dir / "api" / key
    raw_path = entry / "response.json"
    md_path = entry / "result.md"
    meta_path = entry / "meta.json"
    if not force and raw_path.is_file() and md_path.is_file() and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return ApiResult(
            markdown=md_path.read_text(encoding="utf-8"),
            elapsed_seconds=float(meta["elapsed_seconds"]),
            cache_hit=True,
            cache_key=key,
        )
    legacy_key = _legacy_cache_key(image, settings.endpoint, settings.user_id)
    legacy_entry = settings.cache_dir / "api" / legacy_key
    legacy_raw = legacy_entry / "response.json"
    legacy_md = legacy_entry / "result.md"
    legacy_meta = legacy_entry / "meta.json"
    if not force and legacy_raw.is_file() and legacy_md.is_file() and legacy_meta.is_file():
        meta = json.loads(legacy_meta.read_text(encoding="utf-8"))
        raw = legacy_raw.read_bytes()
        markdown = legacy_md.read_text(encoding="utf-8")
        _atomic_write(raw_path, raw)
        _atomic_write(md_path, markdown.encode("utf-8"))
        migrated = {**meta, "migrated_from_cache_key": legacy_key}
        _atomic_write(
            meta_path,
            json.dumps(migrated, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return ApiResult(
            markdown=markdown,
            elapsed_seconds=float(meta["elapsed_seconds"]),
            cache_hit=True,
            cache_key=key,
        )

    settings.require_api_key()
    body, boundary = _multipart(image, settings.user_id, settings.api_key)
    last_error: Exception | None = None
    for attempt in range(settings.request_retries + 1):
        started = time.perf_counter()
        request = urllib.request.Request(
            settings.endpoint,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.request_timeout_seconds) as response:
                raw = response.read()
                status = response.status
            if status != 200:
                raise RuntimeError(f"FinixDoc API HTTP {status}")
            markdown = extract_markdown(raw)
            elapsed = time.perf_counter() - started
            meta = {
                "image_name": image.name,
                "image_sha256": _sha256_file(image),
                "elapsed_seconds": round(elapsed, 3),
                "user_id": settings.user_id,
                "endpoint": settings.endpoint,
            }
            _atomic_write(raw_path, raw)
            _atomic_write(md_path, markdown.encode("utf-8"))
            _atomic_write(meta_path, json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))
            return ApiResult(markdown, elapsed, False, key)
        except (
            urllib.error.URLError,
            http.client.RemoteDisconnected,
            TimeoutError,
            ConnectionError,
            RuntimeError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            if attempt >= settings.request_retries:
                break
            time.sleep(min(20.0, (2**attempt) * 2.0 + random.random()))
    raise RuntimeError(f"FinixDoc API 调用失败，已重试: {last_error}") from last_error


def import_cached_response(
    image: Path,
    raw_response: Path,
    settings: Settings,
    elapsed_seconds: float = 0.0,
) -> ApiResult:
    """Seed the content-addressed cache from a previously saved response."""
    raw = raw_response.read_bytes()
    markdown = extract_markdown(raw)
    key = _cache_key(image, settings.endpoint)
    entry = settings.cache_dir / "api" / key
    meta = {
        "image_name": image.name,
        "image_sha256": _sha256_file(image),
        "elapsed_seconds": round(float(elapsed_seconds), 3),
        "user_id": settings.user_id,
        "endpoint": settings.endpoint,
        "imported": True,
    }
    _atomic_write(entry / "response.json", raw)
    _atomic_write(entry / "result.md", markdown.encode("utf-8"))
    _atomic_write(
        entry / "meta.json",
        json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"),
    )
    return ApiResult(markdown, float(elapsed_seconds), True, key)
