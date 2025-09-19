#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/utils/config.py
# 模組用途
#   統一載入環境參數與預設值（離線安全）。
from __future__ import annotations

import os
from typing import Any


def load_env() -> dict[str, Any]:
    """參數: 無；回傳: 主要環境字典。"""
    return {
        "OFFLINE": os.environ.get("OFFLINE", ""),
        "SMA_ROOT": os.environ.get("SMA_ROOT", ""),
        "SMA_EML_DIR": os.environ.get("SMA_EML_DIR", ""),
        "SMA_OUT_ROOT": os.environ.get("SMA_OUT_ROOT", ""),
    }
