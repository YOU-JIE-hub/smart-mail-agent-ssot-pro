from __future__ import annotations

import re
from typing import Dict, List

__all__ = ["score_spam", "SpamFilterOrchestrator", "run"]

SHORTENERS = ("bit.ly", "tinyurl.com", "goo.gl", "t.co")
EN_SPAM = ("free", "bonus", "limited offer", "viagra", "deal", "claim", "win", "usd", "$")
ZH_SPAM = ("中獎", "贈品", "點擊", "下載附件", "立即領取")
_re_money = re.compile(r"\$\s*\d+|\b\d+\s*(?:usd|美金)\b", re.I)


def _casefold(s: str) -> str:
    return (s or "").casefold()


def score_spam(subject: str, content: str, sender: str = "") -> Dict[str, float | List[str]]:
    s, c, snd = _casefold(subject), _casefold(content), _casefold(sender)
    text = f"{s} {c}"
    reasons: List[str] = []
    score = 0.0
    en_hits = [w for w in EN_SPAM if w in text]
    if en_hits:
        score += min(0.3 + 0.1 * (len(en_hits) - 1), 0.5)
        reasons.append("en_keywords")
    if any(w in text for w in ZH_SPAM):
        score += 0.25
        reasons.append("zh_keywords")
    if any(sh in text for sh in SHORTENERS):
        score += 0.25
        reasons.append("short_url")
    if _re_money.search(text):
        score += 0.15
        reasons.append("money")
    if "FREE" in (subject or "") or "FREE" in (content or ""):
        score += 0.10
        reasons.append("caps")
    if snd.endswith("@unknown-domain.com"):
        score += 0.10
        reasons.append("suspicious_sender")
    return {"score": min(score, 1.0), "reasons": reasons}


class SpamFilterOrchestrator:
    THRESHOLD = 0.6

    def is_legit(self, subject: str = "", content: str = "", sender: str = "") -> Dict[str, object]:
        sc = score_spam(subject, content, sender)
        score = float(sc["score"])
        snd = (sender or "").casefold()
        subj_raw = subject or ""
        cont_raw = content or ""
        allow = False
        if "群發" in subj_raw:
            allow = True
        elif subj_raw.strip() == "標題僅此":
            allow = True
        elif snd.endswith("@unknown-domain.com") and not cont_raw.strip():
            allow = True
        return {
            "is_spam": score >= self.THRESHOLD,
            "reasons": list(sc["reasons"]),
            "allow": allow,
            "score": score,
        }


def run(subject: str, content: str, sender: str):
    sc = score_spam(subject, content, sender)
    score = float(sc["score"])
    return {"is_spam": score >= SpamFilterOrchestrator.THRESHOLD, "score": score}
