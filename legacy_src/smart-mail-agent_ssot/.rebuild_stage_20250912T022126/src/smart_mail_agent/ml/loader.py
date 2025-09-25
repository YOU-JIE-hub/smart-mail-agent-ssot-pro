from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

try:
    import joblib
except Exception:
    joblib = None

STORE = Path("reports_auto/artifacts_store")
LOGDIR = Path("reports_auto/models/inference_logs")
LOGDIR.mkdir(parents=True, exist_ok=True)


def _load_joblib_if_any(d: Path):
    if not joblib:
        return None
    for p in list(d.glob("*.joblib")) + list(d.glob("*.pkl")):
        try:
            return joblib.load(p, mmap_mode="r", mmap_mode="r")
        except Exception:
            continue
    return None


def _log(kind: str, payload: dict[str, Any]) -> None:
    ts = int(time.time())
    (LOGDIR / f"{kind}_{ts}.jsonl").write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def predict_spam(text: str) -> dict[str, Any]:
    d = STORE / "spam"
    model = _load_joblib_if_any(d)
    score = 0.0
    label = "ham"
    if model and hasattr(model, "predict_proba"):
        try:
            # 非嚴格版：把文字包成單樣本
            prob = float(model.predict_proba([text])[0][-1])
            score = prob
            label = "spam" if prob >= 0.5 else "ham"
        except Exception:
            pass
    if score == 0.0:
        # 降級：簡單規則
        kws = ["free", "win", "prize", "信用貸款", "比特幣", "transfer", "urgent"]
        score = sum(k in text.lower() for k in kws) / max(1, len(kws))
        label = "spam" if score >= 0.3 else "ham"
    out = {"task": "spam", "label": label, "score": round(score, 4)}
    _log("spam", {"text": text, **out})
    return out


def predict_intent(text: str) -> dict[str, Any]:
    d = STORE / "intent"
    model = _load_joblib_if_any(d)
    label = "other"
    if model and hasattr(model, "predict") and hasattr(model, "predict_proba"):
        try:
            pred = model.predict([text])[0]
            proba = max(model.predict_proba([text])[0])
            return {"task": "intent", "label": str(pred), "score": float(proba)}
        except Exception:
            pass
    # 降級：正則/關鍵字
    if re.search(r"\b(quote|報價|price|報價單)\b", text, re.I):
        label = "quote"
    elif re.search(r"\b(refund|退款|退費)\b", text, re.I):
        label = "refund"
    elif re.search(r"\b(ticket|bug|issue|錯誤)\b", text, re.I):
        label = "support"
    else:
        label = "other"
    _log("intent", {"text": text, "label": label, "score": 1.0 if label != "other" else 0.5})
    return {"task": "intent", "label": label, "score": 1.0 if label != "other" else 0.5}


def extract_kie(text: str) -> dict[str, Any]:
    d = STORE / "kie_min_bundle_20250831-1644"
    model = _load_joblib_if_any(d)  # 如果真有可用的 KIE joblib
    result = {}
    if model and hasattr(model, "transform"):
        try:
            result = model.transform([text])  # 自定義
            return {"task": "kie", "fields": result}
        except Exception:
            pass
    # 降級：簡單抽取
    m_amt = re.search(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text)
    m_dt = re.search(r"(20[0-9]{2}[-/][01]?[0-9][-/.][0-3]?[0-9])", text)
    m_po = re.search(r"\b(PO[- ]?\d{3,8})\b", text, re.I)
    if m_amt:
        result["amount"] = m_amt.group(1)
    if m_dt:
        result["date"] = m_dt.group(1)
    if m_po:
        result["po"] = m_po.group(1).upper()
    _log("kie", {"text": text, "fields": result})
    return {"task": "kie", "fields": result}
