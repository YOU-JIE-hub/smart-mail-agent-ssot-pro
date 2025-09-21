from __future__ import annotations

import os
from typing import Any, Dict

from smart_mail_agent.utils.logger import get_logger

logger = get_logger("ai_rpa.nlp_llm")


def summarize(text: str, model: str | None = None) -> Dict[str, Any]:
    """
    使用 OpenAI 1.x 介面摘要文字；若未設 OPENAI_API_KEY 則退化為簡單摘要（前 200 字）。
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY 未設置，改用退化摘要")
        return {
            "provider": "fallback",
            "summary": (text[:200] + ("..." if len(text) > 200 else "")),
        }
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        mdl = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        prompt = f"用繁體中文摘要以下內容（100字內）：\n\n{text}"
        resp = client.chat.completions.create(
            model=mdl, messages=[{"role": "user", "content": prompt}], temperature=0.2
        )
        content = resp.choices[0].message.content.strip()
        return {"provider": "openai", "model": mdl, "summary": content}
    except Exception as e:
        logger.exception("LLM 摘要失敗，改用退化摘要：%s", e)
        return {
            "provider": "fallback",
            "error": str(e),
            "summary": (text[:200] + ("..." if len(text) > 200 else "")),
        }
