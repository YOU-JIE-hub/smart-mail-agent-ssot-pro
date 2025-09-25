from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from ai_rpa import spam_adapter

_DEFAULT_RULES: Dict[str, Any] = {
    "keywords": ["free money", "btc", "bitcoin", "usdt", "viagra", "空投", "返利", "暴富"],
    "headers": {"X-Spam-Flag": "YES", "X-Spam-Status": "Yes"},
    "thresholds": {"block": 0.6, "warn": 0.3, "adapter_block": 0.5},
    "adapter_block": 0.5,  # 舊測試相容（頂層）
}

def load_default_ruleset() -> Dict[str, Any]:
    return {
        "keywords": list(_DEFAULT_RULES["keywords"]),
        "headers": dict(_DEFAULT_RULES["headers"]),
        "thresholds": dict(_DEFAULT_RULES["thresholds"]),
        "adapter_block": float(_DEFAULT_RULES["adapter_block"]),
    }

def _header_layer(headers: Optional[Dict[str, str]], rules: Dict[str, Any]) -> Tuple[float, List[str]]:
    if not headers:
        return 0.0, []
    hs = rules.get("headers", {})
    reasons: List[str] = []
    score = 0.0
    for k, v in hs.items():
        hv = headers.get(k)
        if hv and str(hv).strip().upper() == str(v).strip().upper():
            reasons.append(f"{k}: {v}")  # 例如 "X-Spam-Flag: YES"
            score = 1.0
    return score, reasons

def _kw_layer(text: str, rules: Dict[str, Any]) -> Tuple[float, List[str]]:
    kws: List[str] = rules.get("keywords", [])
    s = (text or "").lower()
    hits = [kw for kw in kws if kw in s]
    score = min(1.0, len(hits) / max(1, len(kws)))
    return score, hits

def detect(text: str, headers: Optional[Dict[str, str]] = None, rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rules = rules or load_default_ruleset()
    th = rules.get("thresholds", {})
    th_block = float(th.get("block", 0.6))
    th_adapter = float(th.get("adapter_block", rules.get("adapter_block", 0.5)))

    header_s, header_rs = _header_layer(headers, rules)
    kw_s, kw_hits = _kw_layer(text or "", rules)

    ad = spam_adapter.score([text or ""])
    adapter_s = float(ad.get("score", 0.0))
    adapter_label = ad.get("label", "ham")

    verdict = "ALLOW"
    reasons: List[str] = []

    if header_s >= 1.0:
        verdict = "BLOCK"
        reasons.extend([f"header: {r}" for r in header_rs])

    if kw_hits or kw_s >= th_block:
        verdict = "BLOCK"
        if kw_hits:
            reasons.append(f"kw_match: {kw_hits[0]}")

    if adapter_label == "spam" and adapter_s >= th_adapter:
        verdict = "BLOCK"
        reasons.append("adapter_high_score")

    return {
        "verdict": verdict,
        "score": adapter_s,
        "reasons": reasons,
        "layers": {"header": header_s, "kw": kw_s, "adapter": adapter_s},
        "thresholds": {"block": th_block, "warn": float(th.get("warn", 0.3)), "adapter_block": th_adapter},
    }
