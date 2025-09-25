from __future__ import annotations

from typing import Any, Dict

from . import rules


def analyze(email: Dict[str, Any]) -> Dict[str, Any]:
    """
    輸入：
      { "sender": str, "subject": str, "content": str, "attachments": list[str|{filename:...}] }
    輸出：
      {"label": str, "score": float, "reasons": list[str], "scores": dict, "points": float}
    """
    res = rules.label_email(email)  # dict 版本
    return dict(res)
