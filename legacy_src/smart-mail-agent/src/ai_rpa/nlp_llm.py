from __future__ import annotations
import os
from typing import Any, Dict

def available() -> bool:
    """
    當 OFFLINE!=1 且存在 OPENAI_API_KEY 視為可用。
    測試環境多為 OFFLINE=1，這裡只提供可檢查的旗標供預熱踩分支。
    """
    return os.getenv("OFFLINE") != "1" and bool(os.getenv("OPENAI_API_KEY"))

def chat(prompt: str, model: str = "gpt-4o-mini", **kwargs: Any) -> Dict[str, Any]:
    """
    輕量 stub：OFFLINE 或無金鑰時不外呼，回傳離線訊息；
    有金鑰時也只做 echo（CI 不依賴真實網路）。
    """
    if not available():
        return {"ok": False, "provider": "openai", "offline": True, "text": "", "model": model}
    # 不真的打外網，避免 CI 依賴
    text = f"[stub:{model}] {prompt[:120]}"
    return {"ok": True, "provider": "openai", "text": text, "model": model}
