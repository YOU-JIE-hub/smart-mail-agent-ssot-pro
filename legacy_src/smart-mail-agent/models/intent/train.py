from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json, re

ART = Path("artifacts/intent")
ART.mkdir(parents=True, exist_ok=True)

LABELS: List[str] = [
    "tech_support",      # 技術支援
    "profile_update",    # 修改資訊
    "policy_qa",         # 規則/流程詢問（RAG 會用）
    "complaint",         # 投訴抱怨
    "biz_quote",         # 業務/報價
    "other",             # 其他
]

# 迷你規則庫（當作訓練後的產物）
LABEL_KEYWORDS: Dict[str, List[str]] = {
    "tech_support": ["無法", "登入", "錯誤", "異常", "bug", "掛了", "卡住", "支援"],
    "profile_update": ["修改", "變更", "更新", "電話", "地址", "姓名", "email", "資料"],
    "policy_qa": ["流程", "規則", "條件", "退款", "機制", "限制", "如何", "怎麼"],
    "complaint": ["抱怨", "投訴", "很失望", "延遲", "沒回覆", "服務差", "不滿"],
    "biz_quote": ["合作", "報價", "方案", "價格", "合約", "商務", "導入", "採購"],
    "other": [],
}

def _tokenize(text: str) -> List[str]:
    # 極簡：中文逐字 + 英數詞
    lower = text.lower()
    zh = re.findall(r"[\u4e00-\u9fff]", lower)
    en = re.findall(r"[a-z0-9]+", lower)
    return zh + en

def train() -> Dict[str, Any]:
    # 這裡當作「離線規則訓練完」的產物輸出
    all_kw: List[str] = sorted({w for arr in LABEL_KEYWORDS.values() for w in arr})
    rules = {
        "labels": LABELS,
        "label_keywords": LABEL_KEYWORDS,
        "keywords": all_kw,              # <-- 測試期望
    }
    (ART / "intent_rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    return rules

def load() -> Dict[str, Any]:
    p = ART / "intent_rules.json"
    if not p.exists():
        return train()
    return json.loads(p.read_text(encoding="utf-8"))

def predict(text: str) -> Dict[str, Any]:
    toks = _tokenize(text)
    rules = load()
    best_label = "other"
    best_hits = 0
    for label in rules["labels"]:
        kws = rules["label_keywords"].get(label, [])
        hits = sum(1 for k in kws if any(k in t for t in toks))
        if hits > best_hits:
            best_hits = hits
            best_label = label
    return {"label": best_label, "hits": best_hits}
