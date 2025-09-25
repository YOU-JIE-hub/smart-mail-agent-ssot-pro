from __future__ import annotations

import re
from typing import Dict, List, Tuple

_URL = re.compile(r"(https?://|tinyurl\.|bit\.ly|t\.co)", re.I)
_MONEY = re.compile(r"\b(\$|\d{1,3}(?:,\d{3})+)\b")
_SPAM_WORDS = ("free", "bonus", "viagra", "限時", "免費")


class SpamFilterOrchestrator:
    def __init__(self, threshold: float = 0.5, explain: bool = False):
        self.threshold = float(threshold)
        self.explain = bool(explain)

    def score(self, subject: str, content: str, sender: str) -> Tuple[float, Dict]:
        text = f"{subject or ''} {content or ''}"
        reasons: List[str] = []
        s = text.lower()
        score = 0.0
        if any(w in s for w in _SPAM_WORDS):
            score += 0.4
            reasons.append("keyword")
        if _URL.search(text):
            score += 0.4
            reasons.append("shortlink/url")
        if _MONEY.search(text):
            score += 0.2
            reasons.append("money")
        result = {"is_spam": score >= self.threshold}
        if self.explain:
            result["reasons"] = reasons
        return score, result
