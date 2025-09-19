#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/spam/ml_spam_filter.py
# 模組用途
#   ML spam 評分骨架（離線安全，若無模型則回傳中性分數）。
from __future__ import annotations

import math


class MLSpamFilter:
    """參數: 允許模型為 None；回傳: predict_proba(text)->float（1=spam）。"""

    def __init__(self, model: object | None = None) -> None:
        self.model = model

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-float(x)))

    def predict_proba(self, text: str) -> float:
        """參數: text；回傳: spam 機率（0~1）。"""
        if hasattr(self.model, "predict_proba"):
            # type: ignore[call-arg]
            proba = float(self.model.predict_proba([text])[0][1])  # type: ignore[index]
            return proba
        if hasattr(self.model, "decision_function"):
            score = float(self.model.decision_function([text])[0])  # type: ignore[attr-defined]
            return self._sigmoid(score)
        if hasattr(self.model, "predict"):
            y = self.model.predict([text])[0]  # type: ignore[attr-defined]
            return 1.0 if int(y) == 1 else 0.0
        return 0.5
