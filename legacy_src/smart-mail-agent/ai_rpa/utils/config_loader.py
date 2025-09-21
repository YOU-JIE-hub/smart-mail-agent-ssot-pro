from __future__ import annotations
import json, os
from pathlib import Path
__all__ = ["load"]
def load(path: str | None = None) -> dict:
    # 測試期：允許環境變數指定路徑；否則回傳空設定
    p = path or os.environ.get("SMA_CONFIG") or ""
    if not p: return {}
    pth = Path(p)
    if not pth.exists(): return {}
    if pth.suffix.lower() in (".json",".ndjson"):
        return json.loads(pth.read_text(encoding="utf-8"))
    # 其它副檔名：一律回空，不拋錯
    return {}
