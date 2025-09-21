from __future__ import annotations

from typing import Any

# 只強制拿到類別；函式 score_spam 以「可選匯入 + 後備 wrapper」處理
try:
    from smart_mail_agent.spam.spam_filter_orchestrator import (
        SpamFilterOrchestrator,  # type: ignore
    )
except Exception:
    # 理論上不會走到這；保險起見給個極小 stub，避免純 import 爆炸
    class SpamFilterOrchestrator:  # type: ignore
        THRESHOLD = 0.6

        def score(self, subject: str, content: str, sender: str = "") -> dict[str, Any]:
            text = f"{subject or ''} {content or ''}".lower()
            score = 0.0
            reasons: list[str] = []
            if any(k in text for k in ("free", "限時", "中獎", "bit.ly")):
                score += 0.35
                reasons.append("keywords")
            return {"score": min(score, 1.0), "reasons": reasons}


# 嘗試帶入核心的 score_spam（若不存在就為 None）
try:
    from smart_mail_agent.spam.spam_filter_orchestrator import (
        score_spam as _core_score_spam,  # type: ignore
    )
except Exception:
    _core_score_spam = None  # type: ignore


def score_spam(subject: str, content: str, sender: str = "") -> dict[str, Any]:
    """統一對外 API；盡量呼叫核心，否則用 Orchestrator 或本地降級規則。"""
    # 1) 有同名核心函式就直接用
    if callable(_core_score_spam):
        return _core_score_spam(subject, content, sender)  # type: ignore[misc]

    # 2) 沒有的話，用 Orchestrator 實例的 .score()（若存在）
    try:
        orch = SpamFilterOrchestrator()
        if hasattr(orch, "score"):
            res = orch.score(subject, content, sender)  # type: ignore[attr-defined]
            if isinstance(res, dict) and "score" in res:
                return res
    except Exception:
        pass

    # 3) 最後保底：本地極簡規則，確保回傳結構穩定
    text = f"{subject or ''} {content or ''}".lower()
    score = 0.0
    reasons: list[str] = []
    if any(k in text for k in ("free", "限時", "優惠", "bit.ly", "短連結", "send money")):
        score += 0.35
        reasons.append("keywords")
    return {"score": min(score, 1.0), "reasons": reasons}


__all__ = ["SpamFilterOrchestrator", "score_spam"]
