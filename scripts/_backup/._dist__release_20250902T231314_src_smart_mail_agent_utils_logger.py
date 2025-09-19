#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/utils/logger.py
# 模組用途
#   提供統一樣式的 logger，所有輸出以 [模組名稱] 前綴顯示。
from __future__ import annotations

import logging
import os
import sys

_FMT = "[%(name)s] %(message)s"


def get_logger(name: str) -> logging.Logger:
    """參數: name；回傳: logging.Logger。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
        logger.setLevel(level)
        h = logging.StreamHandler(stream=sys.stdout)
        h.setFormatter(logging.Formatter(_FMT))
        logger.addHandler(h)
    return logger
