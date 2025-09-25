#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/ml_spam_classifier.py
# 模組用途：相容 shim，如有正式實作則轉接；否則提供 predict_proba 最小介面
from __future__ import annotations

try:
    from ..ml_spam_classifier import *  # type: ignore  # noqa: F401,F403
except Exception:

    def predict_proba(features: dict) -> float:
        s = str(features)
        return 0.9 if ("中獎" in s or "lottery" in s) else 0.1
