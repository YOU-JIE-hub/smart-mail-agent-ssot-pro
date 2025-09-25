from __future__ import annotations
import unicodedata, re
from typing import Dict, List, Iterable, Any
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

__all__ = ["analyze_text"]

_SALES_PATTERNS = [
    r"合作", r"商務", r"報價", r"詢價", r"比價", r"採購", r"導入", r"試用", r"方案",
    r"\bquote\b", r"\bpricing\b", r"\bprice\b", r"\bsales?\b", r"\brfq\b",
    r"\bquotation\b", r"\bpurchase\b",
]
_SUPPORT_PATTERNS = [
    r"退款", r"退貨", r"客服", r"維修", r"保固", r"抱怨", r"發票", r"錯帳", r"取消訂單", r"發票重寄",
    r"\bsupport\b", r"\brefunds?\b", r"\breturn(s|ing)?\b", r"\bwarranty\b",
    r"\binvoice\b", r"\bcancel\b", r"\b(issue|problem|bug)s?\b",
]

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    return re.sub(r"\s+", " ", s)

def _match_any(text: str, patterns: Iterable[str]) -> bool:
    for pat in patterns or []:
        if re.search(pat, text, flags=re.I):
            return True
    return False

def _match_all(text: str, patterns: Iterable[str]) -> bool:
    pats = list(patterns or [])
    if not pats:
        return True
    for pat in pats:
        if not re.search(pat, text, flags=re.I):
            return False
    return True

def _match_none(text: str, patterns: Iterable[str]) -> bool:
    for pat in patterns or []:
        if re.search(pat, text, flags=re.I):
            return False
    return True

def _offline_keyword_intents(texts: Iterable[str]) -> List[str]:
    t = " ".join(_norm(x) for x in (texts or []))
    intents: List[str] = []
    if _match_any(t, _SUPPORT_PATTERNS):
        intents.append("support")
        intents.append("refund")
    if _match_any(t, _SALES_PATTERNS):
        intents.append("sales")
        intents.append("quote")
    # 去重但保留順序
    seen, dedup = set(), []
    for k in intents:
        if k not in seen:
            seen.add(k)
            dedup.append(k)
    return dedup

def _load_rules(model: str) -> Dict[str, Any] | None:
    if not model.startswith("rules:"):
        return None
    path_str = model.split(":", 1)[1].strip()
    if not path_str or path_str in {"default", "defaults"}:
        base = Path(__file__).parent / "nlp_rules" / "default.yaml"
        path = base
    else:
        path = Path(path_str)
    if yaml is None:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None

def _intents_via_rules(texts: Iterable[str], rules: Dict[str, Any]) -> List[str]:
    t = " ".join(_norm(x) for x in (texts or []))
    intents_cfg = ((rules or {}).get("intents") or {})
    picked: List[str] = []
    seen = set()
    for name, spec in intents_cfg.items():
        any_p = (spec or {}).get("any", []) or []
        all_p = (spec or {}).get("all", []) or []
        none_p = (spec or {}).get("none", []) or []
        if _match_any(t, any_p) and _match_all(t, all_p) and _match_none(t, none_p):
            if name not in seen:
                seen.add(name)
                picked.append(name)
    return picked

def analyze_text(texts: List[str] | str, *, model: str = "offline-keyword") -> Dict[str, object]:
    """
    texts: 可為單一字串或多段文字
    model:
      - "offline-keyword": 使用關鍵字規則
      - "rules:<yaml_path>"：使用資料驅動規則（支援 any/all/none）
      - 其他（例如 "transformers"）: 在此最小實作中回退到離線規則
    """
    if isinstance(texts, str):
        texts = [texts]

    intents: List[str]
    if model.startswith("rules:"):
        rules = _load_rules(model)
        intents = _intents_via_rules(texts, rules or {})
        # 若規則未載入成功則退回 offline 關鍵字
        if not intents:
            intents = _offline_keyword_intents(texts)
    elif model == "offline-keyword":
        intents = _offline_keyword_intents(texts)
    else:
        # transformers 等：簡化為 fallback
        intents = _offline_keyword_intents(texts)

    # labels 僅保留主要類別（refund / sales），順序依 intents 出現順序
    labels: List[str] = []
    for k in intents:
        if k in ("refund", "sales") and k not in labels:
            labels.append(k)

    length = sum(len(x or "") for x in texts or [])
    return {"intents": intents, "labels": labels, "length": length}
