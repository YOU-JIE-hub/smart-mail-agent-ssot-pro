from __future__ import annotations

import re
from typing import Dict

_SHORTLINK_RE = re.compile(r"(?:\b(?:t\.co|tinyurl\.com|bit\.ly)/[A-Za-z0-9]+)", re.I)
_EN_SPAM = re.compile(r"\b(free|viagra|lottery|winner)\b", re.I)
_ZH_SPAM = re.compile(r"(免費|限時|優惠|中獎)")


class SpamFilterOrchestrator:
    def is_legit(self, subject: str, content: str, sender: str) -> Dict[str, object]:
        text = " ".join([subject or "", content or "", sender or ""])
        reasons = []
        spam = False

        if _SHORTLINK_RE.search(text):
            spam = True
            reasons.append("shortlink")
        if _EN_SPAM.search(text):
            spam = True
            reasons.append("en_keywords")
        if _ZH_SPAM.search(text):
            spam = True
            reasons.append("zh_keywords")

        return {"is_spam": spam, "reasons": reasons}
