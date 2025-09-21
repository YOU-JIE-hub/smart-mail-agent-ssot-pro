from __future__ import annotations
from typing import Iterable, Dict

__all__ = ["score"]

# 極簡本地邏輯（測試會 monkeypatch 掉這個函數；此為 fallback）
_SPAM_HINTS = ("free money", "win prize", "bitcoin", "lottery", "點我領取", "快速致富")

def score(texts: Iterable[str]) -> Dict[str, object]:
    """
    給一組文字，回傳 {'label': 'spam'|'ham', 'score': float(0~1)}
    - 測試可 monkeypatch 這個函數以返回固定結果
    - 真實場景可在這裡掛 LightGBM/HF 模型/外部服務
    """
    blob = " ".join((t or "") for t in (texts or []))
    hit = any(h in blob.lower() for h in _SPAM_HINTS)
    return {"label": "spam" if hit else "ham", "score": 0.9 if hit else 0.1}
