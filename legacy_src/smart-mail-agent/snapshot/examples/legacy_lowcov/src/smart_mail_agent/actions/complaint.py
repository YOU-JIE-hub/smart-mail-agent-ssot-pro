from __future__ import annotations

import json
import sys

#!/usr/bin/env python3
# 檔案位置：src/actions/complaint.py
# 模組用途：處理投訴；計算嚴重度並輸出 SLA_eta / priority / next_step
import uuid
from typing import Any

ACTION_NAME = "complaint"

HIGH_KW = [
    "無法使用",
    "系統當機",
    "down",
    "資料外洩",
    "資安",
    "違法",
    "詐騙",
    "嚴重",
    "停機",
    "崩潰",
    "災難",
    "退款失敗",
    "威脅",
    "主管機關",
]
MED_KW = ["錯誤", "bug", "延遲", "慢", "異常", "問題", "不穩", "失敗"]
LOW_KW = ["建議", "希望", "改善", "回饋", "詢問"]


def _severity(text: str) -> str:
    t = text.lower()
    if any(k.lower() in t for k in HIGH_KW):
        return "high"
    if any(k.lower() in t for k in MED_KW):
        return "med"
    return "low"


def _sla_priority(severity: str) -> tuple[str, str]:
    if severity == "high":
        return ("4h", "P1")
    if severity == "med":
        return ("1d", "P2")
    return ("3d", "P3")


def execute(request: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    subject = str(request.get("subject") or "")
    body = str(request.get("body") or "")
    sev = _severity(subject + "\n" + body)
    sla, pri = _sla_priority(sev)
    req_id = (request.get("meta") or {}).get("request_id") or uuid.uuid4().hex[:12]

    meta = dict(request.get("meta") or {})
    meta.update(
        {
            "severity": sev,
            "SLA_eta": sla,
            "priority": pri,
            "request_id": req_id,
            "next_step": "建立工單並通知負責窗口",
        }
    )

    return {
        "action_name": ACTION_NAME,
        "subject": "[自動回覆] 客訴已受理",
        "body": f"我們已收到您的反映並建立處理流程。嚴重度：{sev}，優先級：{pri}，SLA：{sla}",
        "attachments": request.get("attachments") or [],
        "meta": meta,
    }


handle = execute
run = execute

if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(execute(payload), ensure_ascii=False))
