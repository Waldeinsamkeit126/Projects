from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    width: int
    height: int
    pixels: int
    aspect_ratio: float
    file_bytes: int

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["path"] = str(self.path)
        return value


@dataclass(frozen=True)
class Crop:
    index: int
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def layout_family(info: ImageInfo) -> str:
    if info.aspect_ratio >= 8.0 and info.width <= 2500:
        return "long_document"
    if info.width >= 3000:
        return "dense_table"
    return "mixed"


def whole_image_limit(info: ImageInfo, default_limit: int) -> int:
    family = layout_family(info)
    if family == "long_document":
        # 4562万像素长图整图实测成功；保守留出输出长度余量。
        return max(default_limit, 60_000_000)
    return default_limit


def image_info(path: Path) -> ImageInfo:
    # 官方数据可信，但像素数远超 Pillow 的通用网页图片安全阈值。
    # 这里只读取JPEG头，不在此函数中解码整张图片。
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path) as image:
            width, height = image.size
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    return ImageInfo(
        path=path,
        width=width,
        height=height,
        pixels=width * height,
        aspect_ratio=height / max(width, 1),
        file_bytes=path.stat().st_size,
    )


def vertical_crop_plan(info: ImageInfo, max_pixels: int, overlap: int) -> list[Crop]:
    """Create deterministic full-width vertical crops.

    This is the safe baseline for long documents. Very wide table sheets are
    flagged by the caller and must not be blindly split across columns.
    """
    crop_height = max(512, max_pixels // max(info.width, 1))
    crop_height = min(crop_height, info.height)
    if crop_height >= info.height:
        return [Crop(0, 0, 0, info.width, info.height)]
    overlap = min(overlap, crop_height // 3)
    step = crop_height - overlap
    result: list[Crop] = []
    top = 0
    while top < info.height:
        bottom = min(top + crop_height, info.height)
        if bottom == info.height:
            top = max(0, bottom - crop_height)
        crop = Crop(len(result), 0, top, info.width, bottom)
        if not result or crop.top != result[-1].top:
            result.append(crop)
        if bottom == info.height:
            break
        top += step
    return result
