from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--left", type=int, required=True)
    parser.add_argument("--top", type=int, required=True)
    parser.add_argument("--right", type=int, required=True)
    parser.add_argument("--bottom", type=int, required=True)
    args = parser.parse_args()
    box = (args.left, args.top, args.right, args.bottom)
    if min(args.left, args.top) < 0 or args.right <= args.left or args.bottom <= args.top:
        raise ValueError(f"invalid crop box: {box}")
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(args.source) as source:
            if args.right > source.width or args.bottom > source.height:
                raise ValueError(f"crop {box} exceeds image size {source.size}")
            crop = source.crop(box).convert("RGB")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            crop.save(args.output, quality=100, subsampling=0)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    print(f"{args.output} box={box} size={crop.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
