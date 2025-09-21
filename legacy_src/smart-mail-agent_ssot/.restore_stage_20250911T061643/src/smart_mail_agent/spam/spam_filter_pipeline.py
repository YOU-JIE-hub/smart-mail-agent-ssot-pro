#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/spam/spam_filter_pipeline.py
# 模組用途
#   載入規則與提取信號（signals），輸出 rule-based 分數。
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SpamSignals:
    """參數: keyword_hits/link_ratio/blacklisted；回傳: dataclass 訊號容器。"""

    keyword_hits: int
    link_ratio: float
    blacklisted: bool


def load_rules(root: Path) -> dict[str, Any]:
    """參數: 專案根；回傳: 規則 dict（若缺則使用內建）。"""
    rule_file = root / "src" / "smart_mail_agent" / "spam" / "rules.yaml"
    try:
        import yaml  # type: ignore

        if rule_file.exists():
            return yaml.safe_load(rule_file.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {
        "keywords_en": ["bitcoin", "usdt", "promo", "limited", "click"],
        "keywords_zh": ["限時", "優惠", "比特幣", "轉帳", "點此"],
        "blacklist_domains": ["scam.biz"],
    }


def rule_score(text: str, sender: str | None, rules: dict[str, Any]) -> SpamSignals:
    """參數: 文字/寄件者/規則；回傳: SpamSignals。"""
    hits = 0
    for kw in (rules.get("keywords_en") or []) + (rules.get("keywords_zh") or []):
        if re.search(re.escape(kw), text, re.I):
            hits += 1
    re_url = re.compile(r"https?://\S+", re.I)
    links = len(re_url.findall(text))
    tokens = max(1, len(text.split()))
    lr = float(links) / float(tokens)

    blk = False
    if sender:
        sender_l = sender.lower()
        for d in rules.get("blacklist_domains", []):
            if sender_l.endswith("@" + d) or sender_l.endswith(d):
                blk = True
                break
    return SpamSignals(keyword_hits=hits, link_ratio=lr, blacklisted=blk)
