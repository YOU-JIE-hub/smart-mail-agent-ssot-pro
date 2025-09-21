#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

# --- 目錄與 __init__.py 準備 ---
mkdir -p src src/smart_mail_agent src/smart_mail_agent/ingestion
for d in src src/smart_mail_agent src/smart_mail_agent/ingestion; do
  [[ -f "$d/__init__.py" ]] || echo "" > "$d/__init__.py"
done

# --- Email Processor 主實作（不再間接 import 任何 route_action）---
cat > src/smart_mail_agent/email_processor.py <<'PY'
from __future__ import annotations
import re, json, datetime
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["extract_fields", "write_classification_result"]

# ---- helpers ----
_CJK_SAFE = r"\u4e00-\u9fff"
_INVALID = re.compile(fr"[^0-9A-Za-z{_CJK_SAFE}]+")
_MULTI_US = re.compile(r"_+")

def _safe_stem(s: Optional[str]) -> str:
    s = _INVALID.sub("_", str(s or "record"))
    s = _MULTI_US.sub("_", s).strip("._") or "record"
    return s

_DATE = re.compile(r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b")
_NUM = re.compile(r"\b(\d{1,3}(?:,\d{3})*|\d+)\b")
_BUDGET = re.compile(r"(?:NTD|NT\$|\$|USD|預算)\s*([0-9,]+)", re.I)
_QTY = re.compile(r"(?:數量|qty|quantity)\s*[:：]?\s*([0-9,]+)", re.I)
_CO = re.compile(r"([^\s，。]*(?:公司|股份有限公司))")

def extract_fields(subject: str, body: str) -> Dict[str, Any]:
    """從主旨/內文盡量擷取常見業務欄位：company / quantity / budget / deadline"""
    s, b = subject or "", body or ""
    text = f"{s}\n{b}"

    # 公司名稱
    company = None
    mco = _CO.search(text)
    if mco:
        company = mco.group(1)

    # 數量
    quantity = None
    mq = _QTY.search(text)
    if mq:
        try:
            quantity = int(mq.group(1).replace(",", ""))
        except Exception:
            quantity = None
    if quantity is None:
        for mn in _NUM.finditer(text):
            v = int(mn.group(1).replace(",", ""))
            if 1 <= v <= 99999:
                quantity = v
                break

    # 預算
    budget = None
    mb = _BUDGET.search(text)
    if mb:
        try:
            budget = int(mb.group(1).replace(",", ""))
        except Exception:
            budget = None

    # 截止日期
    deadline = None
    md = _DATE.search(text)
    if md:
        y, m, d = md.group(1), md.group(2), md.group(3)
        deadline = f"{y}-{m}-{d}"

    return {
        "company": company,
        "quantity": quantity,
        "budget": budget,
        "deadline": deadline,
    }

def write_classification_result(
    result: Optional[Dict[str, Any]] = None,
    *,
    subject: Optional[str] = None,
    sender: Optional[str] = None,
    body: Optional[str] = None,
    predicted_label: Optional[str] = None,
    confidence: Optional[float] = None,
    fields: Optional[Dict[str, Any]] = None,
    out_dir: Optional[str] = None,
) -> str:
    """
    將分類結果寫入對應資料夾，回傳輸出檔路徑（字串）。
    - 若提供 result（dict），其餘參數可省略。
    - 依 label 自動路徑：sales/send_quote -> data/leads，complaint -> data/complaints，其餘 -> data/output
    """
    r = dict(result or {})
    if subject is not None: r.setdefault("subject", subject)
    if sender is not None:  r.setdefault("from", sender)
    if body is not None:    r.setdefault("body", body)
    if predicted_label is not None: r.setdefault("predicted_label", predicted_label)
    if confidence is not None:      r.setdefault("confidence", confidence)
    if fields is not None:          r.setdefault("fields", dict(fields))

    lbl = (r.get("predicted_label") or "").lower()
    base = out_dir or (
        "data/leads" if lbl in ("sales_inquiry", "send_quote") else
        ("data/complaints" if "complaint" in lbl else "data/output")
    )
    Path(base).mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(r.get("subject") or r.get("fields", {}).get("company") or r.get("from"))
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    outp = Path(base) / f"{stem}_{ts}.json"

    payload = {
        "subject": r.get("subject"),
        "from": r.get("from"),
        "predicted_label": r.get("predicted_label"),
        "confidence": float(r.get("confidence") or 0.0),
        "created_at": ts,
        "fields": r.get("fields") or extract_fields(r.get("subject") or "", r.get("body") or ""),
    }
    outp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(outp)
PY

# --- Ingestion re-export：不再 import action_handler / route_action ---
cat > src/smart_mail_agent/ingestion/email_processor.py <<'PY'
from __future__ import annotations
from smart_mail_agent.email_processor import extract_fields, write_classification_result
__all__ = ["extract_fields", "write_classification_result"]
PY

# --- 頂層轉接（部分測試會 from email_processor import ...）---
cat > src/email_processor.py <<'PY'
from __future__ import annotations
from smart_mail_agent.email_processor import extract_fields, write_classification_result
__all__ = ["extract_fields", "write_classification_result"]
PY

# --- 測試包 __init__.py，避免 import file mismatch ---
for d in tests tests/sma tests/_ai_min_suite; do
  [[ -d "$d" ]] && ([[ -f "$d/__init__.py" ]] || echo "" > "$d/__init__.py")
done

# --- 清除快取檔 ---
find . -type d -name "__pycache__" -prune -exec rm -rf {} + || true
find . -type f -name "*.pyc" -delete || true

echo "✅ email_processor 實作與 re-export 就緒、測試資料夾已標記為套件、快取已清。"
