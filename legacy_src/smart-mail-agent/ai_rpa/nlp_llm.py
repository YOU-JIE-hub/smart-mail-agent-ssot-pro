#!/usr/bin/env python3
# 檔案位置：ai_rpa/nlp_llm.py
# 模組用途：提供最小「可匯入」的 LLM 介面以通過單測。OFFLINE=1 下回傳固定結果。
from __future__ import annotations
from typing import Any, Dict

def analyze_text(text: str, **kwargs: Any) -> Dict[str, Any]:
  """
  參數：
    text: 待分析文字
    **kwargs: 兼容舊呼叫簽章（忽略）
  回傳：
    dict：最小結構，避免打外網。
  """
  return {
      "final": "other",
      "label": "other",
      "p1": 0.0,
      "score": 0.0,
      "confidence": 0.0,
      "reason": "offline_stub",
  }
