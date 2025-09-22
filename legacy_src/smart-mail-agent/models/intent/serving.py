from __future__ import annotations
from typing import Dict, Any, List
import re

from . import train as intent_train

_SYNONYMS: Dict[str, List[str]] = {
    "biz_quote": ["sales", "quote"],
    "tech_support": ["support", "tech_support"],
    "profile_update": ["profile_update", "update_info"],
    "policy_qa": ["policy", "qa"],
    "complaint": ["complaint"],
    "other": ["other"],
}

def _tokenize(text: str) -> List[str]:
    lower = text.lower()
    zh = re.findall(r"[\u4e00-\u9fff]", lower)
    en = re.findall(r"[a-z0-9]+", lower)
    return zh + en

def predict(text: str) -> Dict[str, Any]:
    toks = _tokenize(text)
    rules = intent_train.load()
    label_scores: Dict[str, int] = {}
    for label in rules["labels"]:
        kws = rules["label_keywords"].get(label, [])
        hits = sum(1 for k in kws if any(k in t for t in toks))
        label_scores[label] = hits

    # 取分數最高的類別（平手時讓 biz_quote 優先，符合「合作/報價」常見文本）
    best = max(label_scores.items(), key=lambda kv: (kv[1], kv[0] == "biz_quote"))[0]
    return {
        "labels": _SYNONYMS.get(best, ["other"]),
        "raw": {"label": best, "scores": label_scores},
    }
