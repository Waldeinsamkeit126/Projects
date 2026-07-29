from __future__ import annotations

import inspect
import json

from paddleocr import PaddleOCR


print(inspect.signature(PaddleOCR))
print(inspect.signature(PaddleOCR.predict))

engine = PaddleOCR(
    text_detection_model_name="PP-OCRv6_tiny_det",
    text_detection_model_dir=r"D:\AFAC2026\models\paddlex\official_models\PP-OCRv6_tiny_det",
    text_recognition_model_name="PP-OCRv6_tiny_rec",
    text_recognition_model_dir=r"D:\AFAC2026\models\paddlex\official_models\PP-OCRv6_tiny_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device="cpu",
    enable_mkldnn=False,
    cpu_threads=8,
)
config = engine._merged_paddlex_config
for key, value in config.items():
    if "limit" in key.lower() or "batch" in key.lower() or "shape" in key.lower():
        print(key, value)
print(json.dumps(config, ensure_ascii=False, indent=2, default=str))
