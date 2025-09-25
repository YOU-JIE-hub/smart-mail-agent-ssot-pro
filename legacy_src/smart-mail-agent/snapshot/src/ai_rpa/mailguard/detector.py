from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Optional

# REVIEW 關鍵字（退訂/行銷）
_RE_REVIEW = [
    re.compile(r"\bunsubscribe\b", re.I),
    re.compile(r"\blimited\s+time\b", re.I),
    re.compile(r"\bcampaign\b", re.I),
]
# BLOCK 關鍵字（典型詐騙/廣告）
_RE_BLOCK = [
    re.compile(r"\bfree\s+money\b", re.I),
    re.compile(r"\bviagra\b", re.I),
    re.compile(r"\bcasino\b", re.I),
]

_RE_URL    = re.compile(r"https?://\S+", re.I)
_RE_BADTLD = re.compile(r"\.(top|xyz|click|work|support)(/|\b)", re.I)
_DOMAIN_RE = re.compile(r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

def _extract_domain(from_header: Optional[str]) -> Optional[str]:
    if not from_header:
        return None
    m = _DOMAIN_RE.search(from_header)
    return m.group(1).lower() if m else None

def _load_list(path: Optional[Path]) -> List[str]:
    if not path:
        return []
    try:
        return [
            line.strip().lower()
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception:
        return []

def load_default_ruleset() -> Dict[str, List[str]]:
    return {
        "review": [r.pattern for r in _RE_REVIEW],
        "block":  [r.pattern for r in _RE_BLOCK],
    }

def detect(
    text: str,
    headers: Optional[Dict[str, str]] = None,
    *,
    allowlist_path: Optional[Path] = None,
    blocklist_path: Optional[Path] = None,
) -> Dict[str, object]:
    """
    回傳:
      {
        "verdict": "ALLOW|REVIEW|BLOCK",
        "score": 0.0~1.0,
        "reasons": [ "kw_review", "kw_review:<pat>", "has_url", "bad_tld",
                     "allowlist", "allowlist:<domain>", ...]
      }
    """
    headers = headers or {}
    reasons: List[str] = []
    score = 0.0

    # allow/blocklist 先決
    domain = _extract_domain(headers.get("From") or headers.get("from"))
    allow = set(_load_list(Path(allowlist_path) if allowlist_path else None))
    block = set(_load_list(Path(blocklist_path) if blocklist_path else None))

    if domain and domain in allow:
        reasons += ["allowlist", f"allowlist:{domain}"]
        return {"verdict": "ALLOW", "score": 0.0, "reasons": reasons}

    if domain and domain in block:
        reasons += ["blocklist", f"blocklist:{domain}"]
        return {"verdict": "BLOCK", "score": 1.0, "reasons": reasons}

    body = text or ""

    matched_review = False
    for rx in _RE_REVIEW:
        if rx.search(body):
            matched_review = True
            reasons += ["kw_review", f"kw_review:{rx.pattern}"]
            score += 0.3

    matched_block = False
    for rx in _RE_BLOCK:
        if rx.search(body):
            matched_block = True
            reasons += ["kw_block", f"kw_block:{rx.pattern}"]
            score += 0.7

    if _RE_URL.search(body):
        reasons.append("has_url")
        score += 0.2
    if _RE_BADTLD.search(body):
        reasons.append("bad_tld")
        score += 0.5

    if matched_block or score >= 0.9:
        verdict = "BLOCK"; score = max(score, 0.9)
    elif matched_review or score >= 0.3:
        verdict = "REVIEW"; score = max(score, 0.3)
    else:
        verdict = "ALLOW"; score = min(score, 0.1)

    return {"verdict": verdict, "score": round(score, 2), "reasons": reasons}
