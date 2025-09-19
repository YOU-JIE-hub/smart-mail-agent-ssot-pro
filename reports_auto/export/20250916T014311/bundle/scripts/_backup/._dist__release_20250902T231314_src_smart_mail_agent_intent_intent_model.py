#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/intent/intent_model.py
# 模組用途
#   定義意圖分類模型的接口/包裝（骨架，供後續擴充）。
from __future__ import annotations

from typing import Any


class IntentModel:
    """參數: 任意模型；回傳: predict(text)->label。"""

    def __init__(self, model: Any | None = None) -> None:
        self.model = model

    def predict(self, text: str) -> str:
        """參數: text；回傳: 標籤字串。"""
        if hasattr(self.model, "predict"):
            y = self.model.predict([text])[0]  # type: ignore[attr-defined]
            return str(y)
        return "other"

    def labels(self) -> list[str]:
        """參數: 無；回傳: 類別清單。"""
        return ["biz_quote", "tech_support", "complaint", "policy_qa", "profile_update", "other"]
