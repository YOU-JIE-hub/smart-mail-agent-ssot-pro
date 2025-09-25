from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

# ---------- 內建 fallback（與 policy_engine.assess_attachments 等價） ----------
_EXEC_EXT = {"exe", "bat", "cmd", "com", "js", "vbs", "scr", "jar", "ps1", "msi", "dll"}


def _assess_fallback(attachments: List[Dict[str, Any]]) -> List[str]:
    risks: List[str] = []
    for a in attachments or []:
        fn = str((a or {}).get("filename", ""))
        mime = str((a or {}).get("mime", "")).lower()
        low = fn.lower()

        parts = [x for x in low.split(".") if x]
        if len(parts) >= 3 and parts[-1] in _EXEC_EXT:
            risks.append("double_ext")

        if "." in low:
            ext = low.rsplit(".", 1)[-1]
            if ext in _EXEC_EXT:
                risks.append(f"suspicious_ext:{ext}")

        if mime == "application/octet-stream" and low.endswith(".pdf"):
            risks.append("octet_stream_pdf")

        if len(fn) > 180 and low.endswith(".pdf"):
            risks.append("suspicious_filename_length")

    out, seen = [], set()
    for r in risks:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


# 優先使用 policy_engine，失敗就用 fallback
try:
    from smart_mail_agent.policy_engine import assess_attachments  # type: ignore
except Exception:
    assess_attachments = _assess_fallback  # type: ignore


def run(payload: Dict[str, Any], *flags: str) -> Dict[str, Any]:
    """最小 CLI 介面：回傳 dict，至少包含 meta.risks（若有）"""
    out: Dict[str, Any] = {
        "action_name": payload.get("predicted_label", "") if isinstance(payload, dict) else "",
        "meta": {},
        "cc": [],
    }
    attachments = payload.get("attachments", []) if isinstance(payload, dict) else []
    try:
        risks = list(dict.fromkeys(assess_attachments(attachments)))  # 去重保序
    except Exception:
        risks = _assess_fallback(attachments)

    # ---------- 最終守門：若應該有 double_ext 但清單沒有，就補上 ----------
    try:
        need_double = any(
            (
                lambda low: (
                    len([x for x in low.split(".") if x]) >= 3
                    and low.rsplit(".", 1)[-1] in _EXEC_EXT
                )
            )(str((a or {}).get("filename", "")).lower())
            for a in (attachments or [])
        )
        if need_double and not any("double_ext" in r for r in risks):
            risks.append("double_ext")
    except Exception:
        pass

    if risks:
        out["meta"]["risks"] = risks

    # 可選偵錯：export SMA_DEBUG_CLI=1 會在 stderr 印出計算過程
    if os.getenv("SMA_DEBUG_CLI") == "1":
        print(f"[cli.debug] __file__={__file__}", file=sys.stderr)
        print(f"[cli.debug] risks={risks}", file=sys.stderr)
    return out
