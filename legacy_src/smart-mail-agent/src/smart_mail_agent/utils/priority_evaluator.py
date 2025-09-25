#!/usr/bin/env python3
from __future__ import annotations

from typing import Literal

from smart_mail_agent.utils.logger import logger

# 檔案位置：src/utils/priority_evaluator.py
# 模組用途：根據主旨、內容、分類與信心分數，評估技術工單的優先等級


PriorityLevel = Literal["high", "medium", "low"]

# 高風險關鍵字（若命中則為 high 優先）
HIGH_RISK_KEYWORDS = [
    "系統故障",
    "服務中斷",
    "登入失敗",
    "掛掉",
    "嚴重錯誤",
    "資料遺失",
    "斷線",
    "無法連線",
]


def contains_critical_keywords(text: str) -> bool:
    """
    判斷文字中是否包含高風險關鍵字

    :param text: 主旨或內文組合文字（小寫）
    :return: 是否命中關鍵字
    """
    return any(kw.lower() in text for kw in HIGH_RISK_KEYWORDS)


def evaluate_priority(
    subject: str,
    content: str,
    sender: str | None = None,
    category: str | None = None,
    confidence: float = 0.0,
) -> PriorityLevel:
    """
    根據分類與信心值評估工單優先順序

    規則：
        - 命中高風險關鍵字  high
        - 技術支援 + 信心 > 0.8  high
        - 投訴與抱怨  medium
        - 詢問流程  low
        - 其他  預設 medium

    :param subject: 信件主旨
    :param content: 信件內文
    :param sender: 寄件人（可選）
    :param category: 分類標籤（可選）
    :param confidence: 分類信心值（可選）
    :return: 優先等級（high, medium, low）
    """
    try:
        combined = f"{subject} {content}".lower()

        if contains_critical_keywords(combined):
            logger.info("[priority_evaluator] 命中高風險詞  優先等級：high")
            return "high"

        if category == "請求技術支援" and confidence >= 0.8:
            logger.info("[priority_evaluator] 技術支援 + 高信心  優先等級：high")
            return "high"

        if category == "投訴與抱怨":
            logger.info("[priority_evaluator] 分類為投訴與抱怨  優先等級：medium")
            return "medium"

        if category == "詢問流程或規則":
            logger.info("[priority_evaluator] 分類為詢問流程  優先等級：low")
            return "low"

        logger.info("[priority_evaluator] 未命中條件  優先等級：medium")
        return "medium"

    except Exception as e:
        logger.error(f"[priority_evaluator] 優先順序判定失敗：{e}")
        return "medium"
