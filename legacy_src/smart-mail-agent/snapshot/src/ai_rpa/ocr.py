#!/usr/bin/env python3
# 檔案位置: src/ai_rpa/ocr.py
# 模組用途: OCR（若無 pytesseract 則優雅退化）
from __future__ import annotations

import os
from typing import Dict

from ai_rpa.utils.logger import get_logger

log = get_logger("OCR")


def run_ocr(image_path: str) -> Dict[str, str]:
    """
    對單一影像路徑執行 OCR。
    回傳: {"path": <str>, "text": <str>}
    """
    try:
        from PIL import Image  # Pillow
    except Exception as e:
        log.warning("缺少 Pillow，返回空結果: %s", e)
        return {"path": image_path, "text": ""}

    try:
        import pytesseract  # type: ignore
    except Exception:
        pytesseract = None  # 允許無 OCR 引擎時的退化

    if not os.path.exists(image_path):
        log.warning("影像不存在: %s", image_path)
        return {"path": image_path, "text": ""}

    try:
        with Image.open(image_path) as im:
            if pytesseract is None:
                return {"path": image_path, "text": ""}
            text = pytesseract.image_to_string(im)  # type: ignore[attr-defined]
            return {"path": image_path, "text": text.strip()}
    except Exception as e:
        log.error("OCR 失敗: %s", e)
        return {"path": image_path, "text": ""}
