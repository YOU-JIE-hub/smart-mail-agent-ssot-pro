from __future__ import annotations
import os
from typing import Any, Iterable, Dict, List

# 規則關鍵字（英文/中文）
KW = {"free money","btc","bitcoin","usdt","viagra","空投","返利","暴富"}

def _as_iter(x: Any) -> Iterable[str]:
    if isinstance(x, (list, tuple, set)):
        for i in x:
            yield str(i)
    else:
        yield str(x)

def _score_rule_str(text: str) -> tuple[float, List[str]]:
    t = (text or "").lower()
    hits = [k for k in KW if k in t]
    return (1.0 if hits else 0.0), [f"kw_match: {h}" for h in hits]

def _score_rule_any(x: Any) -> Dict[str, Any]:
    scores: List[float] = []
    reasons: List[str] = []
    for s in _as_iter(x):
        sc, rs = _score_rule_str(s)
        scores.append(sc)
        reasons.extend(rs)
    score = max(scores) if scores else 0.0
    return {"score": float(score), "reasons": reasons}

def _score_ml_any(x: Any):
    """回傳 {"score": prob, "reasons":[...]} 或 None（不可用/失敗）。"""
    try:
        from models.spam import serving_ml as _sml
        if not getattr(_sml, "available", lambda: False)():
            return None
        scores: List[float] = [float(_sml.score_prob_spam(s)) for s in _as_iter(x)]
        score = max(scores) if scores else 0.0
        return {"score": float(score), "reasons": ["ml_prob"]}
    except Exception:
        return None

def score(x: Any) -> Dict[str, Any]:
    """接受 str 或 Iterable[str]；環境變數 SMA_SPAM_BACKEND=ml 則採用 ML，否則規則。"""
    if os.getenv("SMA_SPAM_BACKEND","").lower() == "ml":
        r = _score_ml_any(x)
        if r is not None:
            return r
    return _score_rule_any(x)
