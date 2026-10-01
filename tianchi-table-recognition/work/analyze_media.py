from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


MEDIA_DIR = Path(r"C:\Users\zhhzh\Documents\Codex\2026-08-26\x20-x20-2\work\competition_data\multimodal_table_recognition\files")

records: list[dict[str, object]] = []
for media_path in sorted(MEDIA_DIR.iterdir()):
    record: dict[str, object] = {
        "name": media_path.name,
        "bytes": media_path.stat().st_size,
        "extension": media_path.suffix.lower(),
    }
    if media_path.suffix.lower() == ".pdf":
        reader = PdfReader(str(media_path))
        page_sizes = []
        text_lengths = []
        for page in reader.pages:
            box = page.mediabox
            page_sizes.append([round(float(box.width), 1), round(float(box.height), 1)])
            try:
                text_lengths.append(len(page.extract_text() or ""))
            except Exception:
                text_lengths.append(0)
        record.update(
            pages=len(reader.pages),
            page_sizes=page_sizes,
            extracted_text_chars=sum(text_lengths),
            pages_with_text=sum(length > 20 for length in text_lengths),
        )
    else:
        with Image.open(media_path) as image:
            record.update(width=image.width, height=image.height, mode=image.mode)
    records.append(record)

pdf_records = [record for record in records if record["extension"] == ".pdf"]
image_records = [record for record in records if record["extension"] != ".pdf"]
summary = {
    "media_files": len(records),
    "pdf_files": len(pdf_records),
    "pdf_pages": sum(int(record["pages"]) for record in pdf_records),
    "pdf_pages_with_text": sum(int(record["pages_with_text"]) for record in pdf_records),
    "image_files": len(image_records),
    "largest_pdf_pages": sorted(
        ({"name": record["name"], "pages": record["pages"]} for record in pdf_records),
        key=lambda item: int(item["pages"]),
        reverse=True,
    )[:10],
    "largest_images": sorted(
        ({"name": record["name"], "width": record["width"], "height": record["height"]} for record in image_records),
        key=lambda item: int(item["width"]) * int(item["height"]),
        reverse=True,
    )[:10],
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
