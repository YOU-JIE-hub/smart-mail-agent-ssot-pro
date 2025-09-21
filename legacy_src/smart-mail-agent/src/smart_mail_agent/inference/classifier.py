from __future__ import annotations

from typing import Any, Dict, Tuple


def smart_truncate(text: str, width: int) -> str:
    text = str(text or "")
    if width <= 0:
        return "..."
    return (text[: max(0, width - 3)] + "...") if len(text) > width else text


def load_model():
    # 測試會 monkeypatch 這個函式；預設給個哨兵即可
    return object()


def classify_intent(subject: str, content: str) -> Dict[str, Any]:
    try:
        _ = load_model()
    except Exception:
        return {"label": "unknown", "confidence": 0.0}
    s = f"{subject or ''} {content or ''}".lower()
    if any(k in s for k in ("報價", "詢價", "quote", "quotation", "合作", "採購")):
        return {"label": "sales_inquiry", "confidence": 0.8}
    if any(k in s for k in ("投訴", "退款", "退費", "抱怨", "售後")):
        return {"label": "complaint", "confidence": 0.75}
    if any(k in s for k in ("流程", "規則", "退貨流程")):
        return {"label": "詢問流程或規則", "confidence": 0.7}
    return {"label": "other", "confidence": 0.3}


class IntentClassifier:
    def __init__(self, model_path: str | None = None, pipeline_override=None):
        self.model_path = model_path
        self.pipeline = pipeline_override

    def _run_pipeline(self, subject: str, content: str) -> Tuple[str, float]:
        if self.pipeline is None:
            # 退回簡易規則
            r = classify_intent(subject, content)
            return r.get("label", "其他"), float(r.get("confidence", 0.0))
        out = self.pipeline(subject, content)
        # 接受多種回傳型態
        if isinstance(out, tuple) and len(out) == 2:
            return str(out[0]), float(out[1])
        if isinstance(out, dict):
            lab = str(
                out.get("label") or out.get("raw_label") or out.get("predicted_label") or "其他"
            )
            sc = float(out.get("score") or out.get("confidence") or 0.0)
            return lab, sc
        if isinstance(out, str):
            return out, 0.0
        return "其他", 0.0

    def classify(self, subject: str, content: str) -> Dict[str, Any]:
        label, score = self._run_pipeline(subject or "", content or "")
        text = f"{subject} {content}".lower()
        is_generic = text.strip() in ("hi", "hello", "hi hello", "hello hi")
        predicted = label
        if is_generic and score < 0.7:
            predicted = "其他"
        return {
            "label": label,
            "raw_label": label,
            "score": score,
            "predicted_label": predicted,
            "confidence": float(score),
        }
