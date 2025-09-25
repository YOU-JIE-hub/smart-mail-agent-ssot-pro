#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/spam/ens.py
# 模組用途
#   Ensemble：規則 + ML 分數 + 門檻（ens_thresholds.json）。
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .ml_spam_filter import MLSpamFilter
from .spam_filter_pipeline import load_rules, rule_score


class SpamEnsemble:
    def _smoke_test(self, m: object) -> bool:
        try:
            if hasattr(m, "predict_proba"):
                _ = m.predict_proba(["hello"])
            elif hasattr(m, "decision_function"):
                _ = m.decision_function(["hello"])
            else:
                _ = m.predict(["hello"])
            return True
        except Exception:
            return False

    """參數: root；回傳: predict()/predict_detail()。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.th = self._load_thresholds()
        self.cut = float(self.th.get("threshold", 0.6))
        self.signals_min = int(self.th.get("signals_min", 2))
        self._m = self._load_model()

    def _load_thresholds(self) -> dict[str, Any]:
        p = self.root / "artifacts_prod" / "ens_thresholds.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"threshold": 0.6, "signals_min": 2}

    def _load_model(self) -> object:
        try:
            import joblib  # type: ignore

            mpath = self.root / "artifacts_prod" / "model_pipeline.pkl"
            if mpath.exists():
                return joblib.load(mpath, mmap_mode="r")
        except Exception:
            pass
        return MLSpamFilter()

    def _proba(self, text: str) -> float:
        if isinstance(self._m, MLSpamFilter):
            return self._m.predict_proba(text)
        if hasattr(self._m, "predict_proba"):
            return float(self._m.predict_proba([text])[0][1])  # type: ignore[index]
        if hasattr(self._m, "decision_function"):
            score = float(self._m.decision_function([text])[0])  # type: ignore[attr-defined]
            return 1.0 / (1.0 + math.exp(-score))
        y = self._m.predict([text])[0]  # type: ignore[attr-defined]
        return 1.0 if int(y) == 1 else 0.0

    def predict_detail(self, text: str) -> dict[str, Any]:
        rules = load_rules(self.root)
        sig = rule_score(text, None, rules)
        p = self._proba(text)
        ens = int((p >= self.cut) or (sig.keyword_hits + int(sig.blacklisted) >= self.signals_min))
        return {
            "proba": p,
            "signals": {"keyword_hits": sig.keyword_hits, "blacklisted": sig.blacklisted, "link_ratio": sig.link_ratio},
            "ens": ens,
            "threshold": self.cut,
            "signals_min": self.signals_min,
        }

    def predict(self, text: str) -> int:
        return self.predict_detail(text)["ens"]  # type: ignore[return-value]
