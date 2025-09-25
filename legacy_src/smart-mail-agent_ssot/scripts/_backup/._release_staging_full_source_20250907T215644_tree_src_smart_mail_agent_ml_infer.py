import re
import time
import traceback
from functools import lru_cache
from typing import Any

from smart_mail_agent.utils.crash import crash_dump
from smart_mail_agent.utils.logger import log_jsonln


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


@lru_cache
def _artifacts_root() -> str:
    return "reports_auto/artifacts_store"


def predict_spam(text: str) -> dict[str, Any]:
    try:
        s = (text or "").lower()
        score = 0.1
        for k in ["buy now", "免費", "點我", "優惠", "bitcoin", "usdt", "博彩"]:
            if k in s:
                score += 0.2
        label = "spam" if score >= 0.5 else "ham"
        obj = {"ok": True, "model": "adapter-spam", "label": label, "score": round(min(score, 1.0), 3), "ts": _now()}
        log_jsonln("ml_spam.jsonl", {"task": "spam", **obj}, redact=True)
        return obj
    except Exception as e:
        crash_dump("ML_SPAM", f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=2)}")
        obj = {"ok": False, "model": "adapter-spam", "error": str(e), "ts": _now()}
        log_jsonln("ml_spam.jsonl", {"task": "spam", **obj})
        return obj


_INTENT_RULES = {
    "quote": ["報價", "詢價", "quote", "價格", "單價", "折扣"],
    "order": ["下單", "採購", "po", "下訂", "數量", "交貨", "下發", "發單"],
    "invoice": ["發票", "統編", "抬頭", "請款", "匯款", "對帳", "收據", "invoice"],
    "logistics": ["出貨", "交期", "lead time", "運費", "追蹤", "宅配", "提單", "隨貨", "物流", "到貨"],
    "warranty": ["保固", "warranty", "RMA", "維修", "退換", "瑕疵", "故障"],
    "general": ["faq", "說明", "規格", "支援", "文件", "說明書", "compatibility", "問題"],
}


def _score_intent(t: str) -> list[tuple[str, float]]:
    s = (t or "").lower()
    scores = []
    for intent, kws in _INTENT_RULES.items():
        sc = 0.0
        for k in kws:
            if k.lower() in s:
                sc += 0.2
        scores.append((intent, min(sc, 0.99)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def predict_intent(text: str) -> dict[str, Any]:
    try:
        ranked = _score_intent(text)
        top1, top1_sc = ranked[0]
        top2, top2_sc = ranked[1]
        needs = True if (top1_sc < 0.4 or (top1_sc - top2_sc) < 0.15) else False
        obj = {
            "ok": True,
            "model": "adapter-intent6",
            "intent": top1,
            "score": round(top1_sc, 3),
            "needs_review": needs,
            "top2": [(top2, round(top2_sc, 3))],
            "ts": _now(),
        }
        log_jsonln("ml_intent.jsonl", {"task": "intent6", **obj}, redact=True)
        return obj
    except Exception as e:
        crash_dump("ML_INTENT6", f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=2)}")
        obj = {"ok": False, "model": "adapter-intent6", "error": str(e), "ts": _now()}
        log_jsonln("ml_intent.jsonl", {"task": "intent6", **obj})
        return obj


def extract_kie(text: str) -> dict[str, Any]:
    try:
        fields = {}
        cov = {}

        def put(k, v):
            fields[k] = v
            cov[k] = 1 if v else 0

        m_amt = re.search(r"(?:NT\$|USD\$|\$)\s?([0-9][0-9,\.]+)", text or "", re.I)
        put("amount", m_amt.group(1) if m_amt else None)
        m_ord = re.search(r"(?:order|訂單|po)[\s#:]*([A-Z0-9\-]{4,})", text or "", re.I)
        put("order_id", m_ord.group(1) if m_ord else None)
        m_vat = re.search(r"(?:統編|VAT|Tax\s?ID)[\s:：]*([0-9A-Za-z\-]{6,12})", text or "", re.I)
        put("vat", m_vat.group(1) if m_vat else None)
        m_inv = re.search(r"(?:抬頭|invoice\s?title)[\s:：]*([^\n\r]{2,40})", text or "", re.I)
        put("invoice_title", m_inv.group(1).strip() if m_inv else None)
        m_trk = re.search(r"(?:追蹤碼|tracking|AWB|提單)[\s#:]*([A-Z0-9\-]{6,})", text or "", re.I)
        put("tracking_no", m_trk.group(1) if m_trk else None)
        m_po = re.search(r"(?:PO)[\s#:]*([A-Z0-9\-]{4,})", text or "", re.I)
        put("po_no", m_po.group(1) if m_po else None)
        m_rma = re.search(r"(?:RMA|維修單)[\s#:]*([A-Z0-9\-]{4,})", text or "", re.I)
        put("rma_no", m_rma.group(1) if m_rma else None)
        obj = {"ok": True, "model": "adapter-kie", "fields": fields, "coverage": cov, "ts": _now()}
        log_jsonln("ml_kie.jsonl", {"task": "kie", **obj}, redact=True)
        return obj
    except Exception as e:
        crash_dump("ML_KIE", f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=2)}")
        obj = {"ok": False, "model": "adapter-kie", "error": str(e), "ts": _now()}
        log_jsonln("ml_kie.jsonl", {"task": "kie", **obj})
        return obj
