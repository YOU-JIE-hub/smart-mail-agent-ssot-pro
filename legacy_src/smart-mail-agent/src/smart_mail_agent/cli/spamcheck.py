from __future__ import annotations

try:
    from smart_mail_agent.utils.spam_filter import (
        SpamFilterOrchestrator,
        score_spam,
    )
except Exception:  # pragma: no cover - legacy fallback
    from modules.spam import SpamFilterOrchestrator, score_spam  # type: ignore


def run(subject: str, content: str, sender: str):
    sc = score_spam(subject, content, sender)
    return {
        "is_spam": float(sc["score"]) >= SpamFilterOrchestrator.THRESHOLD,
        "score": float(sc["score"]),
    }
