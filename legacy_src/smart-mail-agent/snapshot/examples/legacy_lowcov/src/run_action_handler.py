from __future__ import annotations

#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def _read_json(p: str | Path) -> dict[str, Any]:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _write_json(p: str | Path, obj: dict[str, Any]) -> None:
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _req_id() -> str:
    return uuid.uuid4().hex[:12]


def _domain(addr: str) -> str:
    m = re.search(r"@([^>]+)$", addr or "")
    return (m.group(1).strip().lower() if m else "").strip()


def decide_action(pred: str | None) -> str:
    mapping = {
        "reply_faq": "reply_faq",
        "send_quote": "send_quote",
        "sales_inquiry": "sales_inquiry",
        "complaint": "complaint",
        "other": "reply_general",
    }
    return mapping.get((pred or "").strip().lower(), "reply_general")


def build_response(
    obj: dict[str, Any], simulate_failure: str | None, dry_run: bool
) -> dict[str, Any]:
    rid = _req_id()
    pred = obj.get("predicted_label")
    action = decide_action(pred)
    attachments: list[dict[str, Any]] = []
    subject = "[自動回覆] 通知"
    body = "處理完成。"
    meta: dict[str, Any] = {"request_id": rid, "dry_run": dry_run, "duration_ms": 0}

    # 策略：附件超限 -> require_review + CC support
    max_bytes = 5 * 1024 * 1024
    atts = obj.get("attachments") or []
    if any((a or {}).get("size", 0) > max_bytes for a in atts):
        meta["require_review"] = True
        meta["cc"] = ["support@company.example"]

    # 白名單網域
    if _domain(obj.get("from", "")) == "trusted.example":
        meta["whitelisted"] = True

    # 各 action 輸出
    if action == "reply_faq":
        subject = "[自動回覆] FAQ 回覆"
        body = "以下為常見問題回覆與說明。"
    elif action == "send_quote":
        subject = "[自動回覆] 報價說明"
        body = "您好，這是報價附件與說明。"
        if simulate_failure:  # 只要帶了 simulate-failure 就走文字備援
            meta["simulate_failure"] = simulate_failure
            content = "PDF 生成失敗，附上文字版報價說明。"
            attachments.append(
                {"filename": "quote_fallback.txt", "size": len(content.encode("utf-8"))}
            )
    elif action == "sales_inquiry":
        subject = "[自動回覆] 商務詢問回覆"
        body = "我們已收到您的商務詢問，附件為需求摘要，稍後由業務與您聯繫。"
        meta["next_step"] = "安排需求澄清會議並由業務跟進"
        md = f"# 商務詢問摘要（{rid}）\n\n- 來信主旨：{obj.get('subject', '')}\n- 來信者：{obj.get('from', '')}\n- 內文：\n{obj.get('body', '')}\n"
        attachments.append({"filename": f"needs_summary_{rid}.md", "size": len(md.encode("utf-8"))})
    elif action == "complaint":
        subject = "[自動回覆] 投訴受理通知"
        body = "我們已受理您的意見，內部將儘速處理。"
        text = (obj.get("body") or "") + " " + (obj.get("subject") or "")
        if re.search(r"down|宕機|無法使用|嚴重|故障", text, flags=re.I):
            meta["priority"] = "P1"
            meta["SLA_eta"] = "4h"
            meta["cc"] = sorted(
                set((meta.get("cc") or []) + ["ops@company.example", "qa@company.example"])
            )

    out = {
        "action_name": action,
        "subject": subject,
        "body": body,
        "attachments": attachments,
        "meta": meta,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dry-run", dest="dry_run", action="store_true")
    # 舊版不帶值、新版可帶值；兩者皆收，預設 const="pdf"
    ap.add_argument("--simulate-failure", nargs="?", const="pdf", default=None)
    args = ap.parse_args()

    obj = _read_json(args.input)
    t0 = time.time()
    out = build_response(obj, args.simulate_failure, args.dry_run)
    out["meta"]["duration_ms"] = int((time.time() - t0) * 1000)

    _write_json(args.output, out)
    print("CLI_output_written", file=sys.stderr)
    print(f"已輸出：{args.output}")
    return 0


# [PATCH] top-level dry_run atexit
try:
    import argparse as _arg
    import atexit
    import json
    from pathlib import Path as _P

    _p = _arg.ArgumentParser(add_help=False)
    _p.add_argument("--output")
    _p.add_argument("--dry-run", action="store_true")
    _args, _ = _p.parse_known_args()

    def _enforce_top_level_dry_run():
        try:
            if _args and _args.output:
                _out = _P(_args.output)
                if _out.exists():
                    _d = json.loads(_out.read_text(encoding="utf-8"))
                    if _args.dry_run and not _d.get("dry_run", False):
                        _d["dry_run"] = True
                        _out.write_text(json.dumps(_d, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass  # 後處理失敗不影響主流程

    atexit.register(_enforce_top_level_dry_run)
except Exception:
    pass

# [PATCH] ensure complaint P1 next_step atexit
try:
    import argparse as _arg2
    import atexit as _ax2
    import json as _j2
    from pathlib import Path as _P2

    _p2 = _arg2.ArgumentParser(add_help=False)
    _p2.add_argument("--output")
    _a2, _ = _p2.parse_known_args()

    def _ensure_p1_next_step():
        try:
            if _a2 and _a2.output:
                _out = _P2(_a2.output)
                if _out.exists():
                    _d = _j2.loads(_out.read_text(encoding="utf-8"))
                    _meta = _d.get("meta") or {}
                    if (
                        _d.get("action_name") == "complaint"
                        and isinstance(_meta, dict)
                        and _meta.get("priority") == "P1"
                        and not _meta.get("next_step")
                    ):
                        _meta["next_step"] = (
                            "啟動P1流程：建立 incident/bridge，通知 OPS/QA，SLA 4h 內回覆客戶"
                        )
                        _d["meta"] = _meta
                        _out.write_text(
                            _j2.dumps(_d, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
        except Exception:
            pass

    _ax2.register(_ensure_p1_next_step)
except Exception:
    pass


if __name__ == "__main__":
    sys.exit(main())
