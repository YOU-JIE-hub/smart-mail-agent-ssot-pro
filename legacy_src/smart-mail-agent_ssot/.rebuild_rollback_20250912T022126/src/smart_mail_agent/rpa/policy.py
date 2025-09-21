from __future__ import annotations

from .rag.provider import AnswerProvider, OpenAIRAGProvider


def answer_policy_question(query: str, kb: dict[str, str] | None = None, provider: AnswerProvider | None = None) -> str:
    # DI：可注入 Provider，未給則優先用 OpenAI，失敗回退規則
    prov = provider or OpenAIRAGProvider()
    text, hits, latency_ms, source = prov.answer(query or "")
    # 最終輸出可再套用模板（此處直接返回）
    return text
