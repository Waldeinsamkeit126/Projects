from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


ALLOWED_USER_IDS = {
    "finixA1001",
    "finixB2002",
    "finixC3003",
    "finixD4004",
    "finixE5005",
}


def load_dotenv(path: Path) -> None:
    """Load a small .env file without adding a runtime dependency."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_root: Path
    cache_dir: Path
    output_dir: Path
    endpoint: str
    user_id: str
    api_key: str
    request_timeout_seconds: int
    request_retries: int
    max_workers: int
    whole_image_max_pixels: int
    crop_max_pixels: int
    crop_overlap_pixels: int

    @classmethod
    def load(cls, project_root: Path) -> "Settings":
        project_root = project_root.resolve()
        load_dotenv(project_root / ".env")
        config_path = project_root / "config.json"
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        user_id = os.getenv("FINIX_USER_ID", "finixB2002")
        if user_id not in ALLOWED_USER_IDS:
            raise ValueError(f"FINIX_USER_ID 不在官方白名单中: {user_id}")
        endpoint = os.getenv(
            "FINIX_API_ENDPOINT",
            "https://finixdocapi.alipay.com/api/finix_doc/call_with_file",
        )
        if endpoint != "https://finixdocapi.alipay.com/api/finix_doc/call_with_file":
            raise ValueError("拒绝向非官方地址发送比赛图片")
        return cls(
            project_root=project_root,
            data_root=Path(raw["data_root"]),
            cache_dir=Path(raw["cache_dir"]),
            output_dir=Path(raw["output_dir"]),
            endpoint=endpoint,
            user_id=user_id,
            api_key=os.getenv("FINIX_API_KEY", ""),
            request_timeout_seconds=int(
                os.getenv("FINIX_REQUEST_TIMEOUT_SECONDS", raw["request_timeout_seconds"])
            ),
            request_retries=int(os.getenv("FINIX_REQUEST_RETRIES", raw["request_retries"])),
            max_workers=int(os.getenv("FINIX_MAX_WORKERS", raw["max_workers"])),
            whole_image_max_pixels=int(raw["whole_image_max_pixels"]),
            crop_max_pixels=int(raw["crop_max_pixels"]),
            crop_overlap_pixels=int(raw["crop_overlap_pixels"]),
        )

    def require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("缺少 FINIX_API_KEY；请复制 .env.example 为 .env 后填写")
