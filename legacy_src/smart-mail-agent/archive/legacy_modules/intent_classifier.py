from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

LabelMap = {
    "faq": "詢問流程或規則",
    "rule": "詢問流程或規則",
    "refund": "詢問流程或規則",
    "policy": "詢問流程或規則",
    "apology": "售後服務或抱怨",
    "complaint": "售後服務或抱怨",
    "support": "售後服務或抱怨",
    "after_sale": "售後服務或抱怨",
    "quote": "業務接洽或報價",
    "pricing": "業務接洽或報價",
    "price": "業務接洽或報價",
    "other": "其他",
}


def _unpack(y: Any) -> Tuple[str, float]:
    if isinstance(y, tuple) and len(y) >= 2:
        return str(y[0]), float(y[1])
    if isinstance(y, dict):
        if "label" in y and ("score" in y or "confidence" in y):
            return str(y["label"]), float(y.get("score", y.get("confidence", 0.0)))
    if isinstance(y, str):
        return y, 0.0
    return "other", 0.0


def _is_generic(subject: str, content: str) -> bool:
    s = f"{subject or ''} {content or ''}".lower()
    return any(w in s for w in ("hi", "hello", "您好", "你好")) and len(s) < 40


class IntentClassifier:
    def __init__(
        self, model_path: str = "dummy", pipeline_override: Callable[[str, str], Any] | None = None
    ):
        self.model_path = model_path
        self.pipeline = pipeline_override

    def _map_label(self, raw: str) -> str:
        r = raw.lower()
        return LabelMap.get(r, "其他")

    def classify(self, subject: str, content: str) -> Dict[str, Any]:
        raw = "other"
        conf = 0.0
        if self.pipeline:
            raw, conf = _unpack(self.pipeline(subject, content))
        mapped = self._map_label(raw)
        # 規則覆蓋
        s = f"{subject or ''} {content or ''}"
        if any(k in s for k in ("報價", "價格")):
            mapped = "業務接洽或報價"
        if any(k in s for k in ("售後", "抱怨", "投訴")):
            mapped = "售後服務或抱怨"
        # Fallback：訊息過於通用且低信心
        if _is_generic(subject, content) and conf < 0.5:
            mapped = "其他"
        return {
            "predicted_label": mapped,
            "raw_label": raw,
            "confidence": float(conf),
            "label": mapped,
        }
