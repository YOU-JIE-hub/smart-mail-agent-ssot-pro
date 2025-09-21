#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/inference_classifier.py
# 模組用途：相容 shim，轉接至 smart_mail_agent.inference_classifier
from __future__ import annotations

from src.smart_mail_agent.inference_classifier import (
    classify_intent,
    load_model,
    smart_truncate,
)

__all__ = ["classify_intent", "load_model", "smart_truncate"]
