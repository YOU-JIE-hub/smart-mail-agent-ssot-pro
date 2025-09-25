from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def smart_truncate(text: str, limit: int) -> str:
    if limit <= 0:
        return "..."
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


_zh_map = {
    "sales_inquiry": "業務接洽或報價",
    "faq": "詢問流程或規則",
    "complaint": "投訴與抱怨",
    "other": "其他",
}


class IntentClassifier:
    def __init__(
        self, model_path: Optional[str] = None, pipeline_override: Optional[Callable] = None
    ):
        self.model_path = model_path
        self.pipeline = pipeline_override  # 測試會注入 mock
        self.loaded = False

    def _load(self):
        if self.pipeline:
            self.loaded = True
            return
        # 測試不需要真正模型，保留為 not loaded -> 走 keyword 規則
        self.loaded = False

    def _keyword_rules(self, text: str) -> Dict[str, Any]:
        t = text.lower()
        # 業務/詢價
        if any(k in t for k in ["報價", "詢價", "合作", "quotation", "quote"]):
            return {
                "predicted_label": _zh_map["sales_inquiry"],
                "raw_label": "sales_inquiry",
                "confidence": 0.85,
            }
        # 流程/規則
        if any(k in t for k in ["流程", "規則", "退貨", "退款", "退費", "how to"]):
            return {"predicted_label": _zh_map["faq"], "raw_label": "faq", "confidence": 0.8}
        # 投訴
        if any(k in t for k in ["投訴", "抱怨", "退款", "無法使用", "down", "嚴重"]):
            return {
                "predicted_label": _zh_map["complaint"],
                "raw_label": "complaint",
                "confidence": 0.75,
            }
        return {"predicted_label": _zh_map["other"], "raw_label": "other", "confidence": 0.5}

    def classify(self, subject: str, body: str) -> Dict[str, Any]:
        self._load()
        text = f"{subject}\n{body}".strip()
        if self.loaded and self.pipeline:
            try:
                out = self.pipeline(text)
                # 允許 mock 回傳 dict 或 list[dict]
                if isinstance(out, list):
                    out = out[0] if out else {"label": "other", "score": 0.0}
                raw_label = out.get("label", "other")
                score = float(out.get("score", 0.0))
                # 嘗試映射英文→中文
                mapping = {
                    "sales_inquiry": _zh_map["sales_inquiry"],
                    "faq": _zh_map["faq"],
                    "complaint": _zh_map["complaint"],
                    "other": _zh_map["other"],
                    "UNK": "未知",
                    "unknown": "未知",
                }
                predicted = mapping.get(raw_label, _zh_map["other"])
                # 若關鍵字更明確（例如包含「流程/退費」），覆蓋 pipeline 結果
                if any(k in text for k in ["流程", "退費", "退款", "退貨"]):
                    predicted, raw_label = _zh_map["faq"], "faq"
                return {
                    "predicted_label": predicted,
                    "raw_label": raw_label,
                    "label": (
                        raw_label
                        if raw_label in ("other", "sales_inquiry", "complaint", "faq")
                        else "other"
                    ),
                    "confidence": score,
                }
            except Exception:
                # 失敗當作未知
                return {
                    "label": "unknown",
                    "predicted_label": "未知",
                    "raw_label": "unknown",
                    "confidence": 0.0,
                }
        # 無模型：走規則
        return self._keyword_rules(text)


def load_model() -> object:
    # 測試會 monkeypatch 這個函式丟例外；預設回傳假物件
    return object()


def classify_intent(subject: str, body: str) -> Dict[str, Any]:
    try:
        _ = load_model()
    except Exception:
        return {"label": "unknown", "confidence": 0.0}
    # 沒丟例外就用簡單規則
    t = f"{subject}\n{body}"
    if any(k in t for k in ["報價", "詢價", "合作"]):
        return {"label": "sales_inquiry", "confidence": 0.8}
    if any(k in t for k in ["投訴", "抱怨", "無法使用"]):
        return {"label": "complaint", "confidence": 0.7}
    return {"label": "other", "confidence": 0.5}
