#!/usr/bin/env python3
from __future__ import annotations

import re

from smart_mail_agent.utils.logger import logger

# 檔案位置：src/spam/rule_filter.py
# 模組用途：使用靜態規則（關鍵字、黑名單、樣式）偵測垃圾郵件內容


class RuleBasedSpamFilter:
    """
    規則式垃圾信過濾器：透過關鍵字、黑名單網域、常見連結樣式進行 spam 偵測。
    """

    def __init__(self):
        # 黑名單網域（若 email 內容包含此網址，視為 spam）
        self.blacklist_domains = ["xxx.com", "freemoney.cn", "spamlink.net"]

        # 可疑 spam 關鍵字（不區分大小寫）
        self.suspicious_keywords = [
            "裸聊",
            "中獎",
            "限時優惠",
            "點我加入",
            "免費試用",
            "現金回饋",
            "賺錢",
            "投資機會",
            "line加好友",
            "情色",
            "財務自由",
            "送你",
            "簡單賺錢",
        ]

        # 常見 spam 連結樣式（正規表達式）
        self.patterns = [
            re.compile(r"https?://[^\s]*\.xxx\.com", re.IGNORECASE),
            re.compile(r"line\s*[:：]?\s*[\w\-]+", re.IGNORECASE),
        ]
        # [SMA] 強化高風險關鍵字
        try:
            self.keywords.extend(
                [
                    "免費中獎",
                    "中獎",
                    "點此領獎",
                    "領獎",
                    "百萬",
                    "點擊領取",
                    "刷卡驗證",
                    "帳號異常",
                    "快速致富",
                    "投資保證獲利",
                ]
            )
        except Exception:
            pass

    def is_spam(self, text: str) -> bool:
        """
        判斷文字是否為垃圾信件內容。

        :param text: 信件主旨與內容合併後的純文字
        :return: bool - 是否為 spam
        """
        text = text.lower()
        logger.debug("[RuleBasedSpamFilter] 進行規則式 Spam 檢查")

        for kw in self.suspicious_keywords:
            if kw in text:
                logger.info(f"[RuleBasedSpamFilter] 偵測關鍵字：{kw}")
                return True

        for domain in self.blacklist_domains:
            if domain in text:
                logger.info(f"[RuleBasedSpamFilter] 偵測黑名單網址：{domain}")
                return True

        for pattern in self.patterns:
            if pattern.search(text):
                logger.info(f"[RuleBasedSpamFilter] 偵測樣式：{pattern.pattern}")
                return True

        return False
