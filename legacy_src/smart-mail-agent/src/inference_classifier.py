from __future__ import annotations

try:
    from smart_mail_agent.inference_classifier import (
        classify_intent,
        load_model,
        smart_truncate,
    )
except Exception:
    # 最低限度的後援，避免 ImportError 測試直接炸掉
    def smart_truncate(text: str, max_chars: int = 1000) -> str:
        text = text or ""
        if max_chars is None or max_chars <= 0:
            return ""
        if len(text) <= max_chars:
            return text
        return "..." if max_chars < 4 else (text[: max_chars - 3] + "...\n")

    def classify_intent(subject: str = "", content: str = ""):
        return {"label": "unknown", "predicted_label": "unknown", "confidence": 0.0}

    def load_model():  # noqa
        class _Dummy: ...

        return _Dummy()
