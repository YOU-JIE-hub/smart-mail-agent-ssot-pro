#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/rpa/policy.py
# 模組用途
#   FAQ/政策回應骨架。
from __future__ import annotations


def answer_policy_question(query: str, kb: dict[str, str] | None = None) -> str:
    """參數: query/kb；回傳: 回覆字串（無 kb 時回覆骨架）。"""
    kb = kb or {"退貨政策": "收到貨 7 天內可退換貨", "SLA": "一般需求 3 個工作日內回覆"}
    q = (query or "").strip()
    for k, v in kb.items():
        if k in q:
            return v
    return "您的問題已收到，我們將儘速回覆。"
