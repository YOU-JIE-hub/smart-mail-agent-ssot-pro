#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/rpa/utils/json_safe.py
# 模組用途
#   JSON 安全檢查。
from __future__ import annotations

import json


def jsonable(obj) -> bool:
    """參數: 任意；回傳: 是否可序列化為 JSON。"""
    try:
        json.dumps(obj)
        return True
    except Exception:
        return False
