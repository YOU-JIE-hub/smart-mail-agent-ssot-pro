from __future__ import annotations
__all__ = ["run_ocr"]
def run_ocr(path: str) -> dict:
    # 測試用：不做真正 OCR，只回固定結構
    return {"text": "", "ok": True, "path": path}
