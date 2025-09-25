#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/llm_scorer.py
# 模組用途：L2 LLM 打分（預設 OFFLINE 啟發式），若 SMA_SPAM_USE_LLM=1 則可接外部 API
from __future__ import annotations
import os, re, json
from typing import List

def score_likelihood(sample: dict) -> float:
    """
    參數：sample（含 subject/body/from/attachments）
    回傳：spam 機率（0~1）
    OFFLINE 預設：以簡單啟發式近似，避免外網依賴
    """
    if os.getenv("SMA_SPAM_USE_LLM","0") != "1":
        text = f"{sample.get('subject','')}\n{sample.get('body','')}".lower()
        hits = 0
        for k in ("verify account","reset your password","urgent","lottery","wire transfer","限時","中獎","驗證帳號","匯款"):
            if k in text: hits += 1
        return min(1.0, 0.2 + 0.15*hits)  # 粗略啟發
    # TODO：接 API（保留擴充點）；此專案預設離線不觸發
    return 0.5
