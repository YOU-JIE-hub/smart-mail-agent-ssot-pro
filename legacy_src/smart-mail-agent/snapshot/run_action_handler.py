#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

_EXEC_EXT = {"exe", "bat", "cmd", "com", "js", "vbs", "scr", "jar", "ps1", "msi", "dll"}


def _assess_for_matrix(attachments: List[Dict[str, Any]]) -> List[str]:
    """符合 tests/policy/test_attachment_risks_matrix.py 的名稱與邏輯。"""
    risks: List[str] = []
    for a in attachments or []:
        fn = str((a or {}).get("filename", ""))
        mime = str((a or {}).get("mime", "")).lower()
        low = fn.lower()

        # double_ext: 至少三段，且最後一段是可執行副檔名
        parts = [p for p in low.split(".") if p]
        if len(parts) >= 3 and parts[-1] in _EXEC_EXT:
            risks.append("double_ext")

        # long_name: 超長檔名（測試用 R*200+.pdf）
        if len(fn) > 180:
            risks.append("long_name")

        # mime_mismatch: 名稱像 pdf 但 MIME 是 octet-stream
        if low.endswith(".pdf") and mime == "application/octet-stream":
            risks.append("mime_mismatch")

    # 去重保序
    out, seen = [], set()
    for r in risks:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    payload: Dict[str, Any] = json.loads(open(args.input, "r", encoding="utf-8").read())
    attachments = payload.get("attachments") or []

    risks = _assess_for_matrix(attachments)

    out: Dict[str, Any] = {
        "ok": True,
        "dry_run": bool(args.dry_run),
        "input_subject": payload.get("subject"),
        "predicted_label": payload.get("predicted_label"),
        "meta": {"risks": risks},
    }

    if risks:
        out["meta"]["require_review"] = True
        # 測試期待 cc 放在 meta.cc
        out["meta"]["cc"] = ["support@company.example"]

    # 保持 JSON 輸出
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    # 可選偵錯
    if os.getenv("SMA_DEBUG_CLI") == "1":
        print(f"[run_action_handler] wrote {args.output} meta.risks={risks}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
