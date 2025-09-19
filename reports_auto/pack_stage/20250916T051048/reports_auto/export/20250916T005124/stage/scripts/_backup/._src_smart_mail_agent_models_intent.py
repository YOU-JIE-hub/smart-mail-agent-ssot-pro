from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple

_FALLBACK_RULES: Dict[str, List[str]] = {
    "報價": ["quote", "報價", "quotation", "報價單", "price", "estimate"],
    "技術支援": ["support", "故障", "bug", "error", "技術", "無法", "登入", "crash"],
    "投訴": ["complaint", "投訴", "抱怨", "很差", "不滿", "退費", "延遲"],
    "規則詢問": ["faq", "規則", "條款", "refund", "退款", "條件", "限制"],
    "資料異動": ["變更", "修改", "更新", "address", "phone", "資料異動", "更正"],
}

class IntentRouter:
    def __init__(self, rules_path: Path = Path("artifacts_prod/intent_rules_calib_v11c.json")):
        self.rules_path = rules_path
        self.rules: Dict[str, List[str]] = dict(_FALLBACK_RULES)
        self.thresholds: Dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if not self.rules_path.exists():
            return
        try:
            data = json.loads(self.rules_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "rules" in data:
                rules = {}
                for r in data["rules"]:
                    lab = r.get("label")
                    kws = r.get("keywords") or r.get("kws") or []
                    if lab and isinstance(kws, list) and kws:
                        rules.setdefault(lab, [])
                        rules[lab].extend([str(k) for k in kws])
                if rules:
                    self.rules = rules
                self.thresholds = {k: float(v) for k, v in (data.get("thresholds") or {}).items()}
            elif isinstance(data, dict):
                ok = all(isinstance(v, list) for v in data.values()) and len(data) > 0
                if ok:
                    self.rules = {k: [str(x) for x in v] for k, v in data.items()}
        except Exception:
            pass

    def predict(self, subject: str, body: str) -> Tuple[str, float, float]:
        text = f"{subject}\n{body}".lower()
        best_label, best_score = "其他", 0.0
        for lab, kws in self.rules.items():
            score = sum(1 for kw in kws if kw and str(kw).lower() in text)
            if score > best_score:
                best_label, best_score = lab, float(score)
        th = self.thresholds.get(best_label, 1.0 if best_label != "其他" else 0.0)
        norm = min(1.0, best_score / 3.0)
        return best_label, norm, th
