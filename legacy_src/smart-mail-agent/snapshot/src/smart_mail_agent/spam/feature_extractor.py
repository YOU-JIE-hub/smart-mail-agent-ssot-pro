#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/feature_extractor.py
# 模組用途：相容 shim，如有正式實作則轉接；否則提供最小介面
from __future__ import annotations

try:
    from ..feature_extractor import *  # type: ignore  # noqa: F401,F403
except Exception:

    def extract_features(subject: str, content: str, sender: str | None = None) -> dict:
        return {
            "len_subject": len(subject or ""),
            "len_content": len(content or ""),
            "has_sender": bool(sender),
        }
