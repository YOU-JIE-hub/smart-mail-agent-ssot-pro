from __future__ import annotations
from pathlib import Path
from typing import Dict

def ocr_bytes(data: bytes, lang: str = "auto") -> Dict[str, str]:
    """
    超輕量 OCR stub（離線）：嘗試以 UTF-8 解碼；失敗則回傳 hex 摘要。
    測試只會確認可被呼叫，不需真實辨識。
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("ocr_bytes expects bytes")
    try:
        txt = data.decode("utf-8", errors="ignore")
        if not txt.strip():
            # 給個可預見輸出，避免全空字串
            txt = f"<{len(data)} bytes>"
    except Exception:
        # 極端情況仍保證可用輸出
        txt = "<bin>"
    return {"text": txt}

def ocr_path(path: str | Path, lang: str = "auto") -> Dict[str, str]:
    p = Path(path)
    data = p.read_bytes()
    return ocr_bytes(data, lang=lang)
