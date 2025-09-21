from __future__ import annotations

import os
from typing import Any

# .env 可有可無；失敗就算了
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# OpenAI 是可選依賴：import 失敗也不阻擋模組匯入
try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _mk_client() -> Any | None:
    # OFFLINE 或沒裝 openai 時，回傳 None 讓呼叫端走離線路徑
    if os.getenv("OFFLINE") == "1" or OpenAI is None:
        return None
    try:
        key = os.getenv("OPENAI_API_KEY")
        return OpenAI(api_key=key) if key else OpenAI()
    except Exception:
        return None


class LLMSpamFilter:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or DEFAULT_MODEL
        self.client = _mk_client()

    def score(self, subject: str, content: str) -> dict[str, Any]:
        text = f"{subject or ''} {content or ''}".lower()

        # 離線 / 無 openai ：提供穩定的本地降級路徑
        if self.client is None:
            score = 0.0
            reasons: list[str] = []
            if any(k in text for k in ("free", "限時", "中獎", "bit.ly", "send money")):
                score += 0.35
                reasons.append("keywords")
            return {"score": min(score, 1.0), "reasons": reasons, "engine": "offline_stub"}

        # 線上路徑（CI 預設 OFFLINE=1 不會走到；留作未來接 API）
        try:
            _ = self.client  # 佯用，避免未使用警告
            # 真正 OpenAI 呼叫省略；避免引入額外相依與測試不穩定
            return {"score": 0.5, "reasons": ["llm_placeholder"], "engine": "openai"}
        except Exception:
            return {"score": 0.0, "reasons": ["llm_error"], "engine": "openai"}


__all__ = ["LLMSpamFilter"]
