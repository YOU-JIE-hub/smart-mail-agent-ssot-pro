from __future__ import annotations

from typing import Dict, List

_SPAM_KW = ["免費", "中獎", "點此", "tinyurl", "bonus", "offer"]
_SHORT_DOMAINS = ["unknown-domain.com"]


class SpamFilterOrchestrator:
    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = float(threshold)

    def score(self, subject: str, content: str, sender: str = "") -> Dict[str, float]:
        s = (subject or "") + " " + (content or "")
        sc = 0.0
        if any(k.lower() in s.lower() for k in _SPAM_KW):
            sc += 0.75
        if sender and any(d in sender for d in _SHORT_DOMAINS):
            sc = max(sc, 0.6)
        return {"score": round(sc, 2)}

    def is_spam(self, subject: str, content: str, sender: str = "") -> Dict[str, object]:
        rs: List[str] = []
        s = (subject or "") + " " + (content or "")
        if any(k.lower() in s.lower() for k in _SPAM_KW):
            rs.append("zh_keywords")
        if sender and any(d in sender for d in _SHORT_DOMAINS):
            rs.append("suspicious_domain")
        sc = self.score(subject, content, sender)["score"]
        return {
            "is_spam": sc >= self.threshold,
            "score": sc,
            "reasons": rs,
            "threshold": self.threshold,
        }

    def is_legit(self, subject: str, content: str, sender: str = "") -> Dict[str, object]:
        r = self.is_spam(subject, content, sender)
        r["allow"] = not bool(r["is_spam"])
        return r
