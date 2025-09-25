from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


def _ext(fname: str) -> str:
    return Path(fname).suffix.lower().lstrip(".")


def _attachment_risks(att: Dict[str, Any]) -> List[str]:
    risks: List[str] = []
    fn = att.get("filename") or ""
    mime = (att.get("mime") or att.get("mimetype") or "").lower()
    size = float(att.get("size") or 0)
    # 雙副檔名
    if re.search(r"\.[A-Za-z0-9]{1,6}\.[A-Za-z0-9]{1,6}$", fn):
        risks.append("attach:double_ext")
    # 檔名過長
    if len(Path(fn).name) > 120:
        risks.append("attach:long_name")
    # MIME 與副檔名大致不符
    ext = _ext(fn)
    if ext == "pdf" and mime and "pdf" not in mime:
        risks.append("attach:mime_mismatch")
    # 大檔 >5MB
    if size >= 5 * 1024 * 1024:
        risks.append("attach:oversize")
    return risks


def _domain(addr: str) -> str:
    m = re.search(r"@([^>]+)>?$", addr or "")
    return (m.group(1) if m else "").lower()


def _subject_prefix(action: str) -> str:
    # 統一使用 [自動回覆]
    return "[自動回覆]"


def _complaint_meta(text: str) -> Dict[str, Any]:
    s = text or ""
    meta: Dict[str, Any] = {}
    if any(k in s for k in ("嚴重", "down", "當機", "無法使用", "影響交易")):
        meta.update(
            priority="P1",
            SLA_eta="4h",
            cc=["ops@company.example", "qa@company.example"],
            next_step="已建立 P1 事件並通知相關單位",
        )
    else:
        meta.update(priority="P2", cc=["ops@company.example", "qa@company.example"])
    return meta


def _apply_policy(
    payload: Dict[str, Any], *, dry: bool, simulate: str | None, whitelist: bool
) -> Dict[str, Any]:
    subject = payload.get("subject") or ""
    sender = payload.get("from") or payload.get("sender") or ""
    label = payload.get("predicted_label") or payload.get("label") or ""
    action_map = {
        "send_quote": "send_quote",
        "reply_faq": "reply_faq",
        "apply_info_change": "apply_info_change",
        "reply_support": "reply_support",
        "reply_apology": "reply_general",
        "sales_inquiry": "sales_inquiry",
        "complaint": "complaint",
        # 中文容錯
        "業務接洽或報價": "sales_inquiry",
        "詢問流程或規則": "reply_faq",
        "售後服務或抱怨": "complaint",
        "其他": "reply_general",
    }
    action = action_map.get(str(label), "reply_general")

    out: Dict[str, Any] = {
        "ok": True,
        "subject": subject,
        "action": action,
        "action_name": action,
        "attachments": [],
        "meta": {"dry_run": bool(dry), "require_review": False, "whitelisted": False},
        "warnings": [],
    }

    # 白名單
    dom = _domain(sender)
    if whitelist or os.getenv("SMA_FORCE_WHITELIST") == "1" or dom.endswith("trusted.example"):
        out["meta"]["whitelisted"] = True

    # 模擬失敗 → 強制人工審查，並標記原因
    if simulate:
        out["meta"]["require_review"] = True
        out["meta"]["simulate_failure"] = simulate
        out["warnings"].append(f"simulated_{simulate}_failure")

    # 附件風險
    atts = payload.get("attachments") or []
    risks_all: List[str] = []
    for a in atts:
        rs = _attachment_risks(a)
        risks_all.extend(rs)
    if risks_all:
        out["meta"]["require_review"] = True
        out["meta"]["risks"] = sorted(set(risks_all))
        cc = out["meta"].setdefault("cc", [])
        if "support@company.example" not in cc:
            cc.append("support@company.example")

    # 動作處理
    prefix = _subject_prefix(action)
    if action == "send_quote":
        out["subject"] = f"[報價] {subject or ''}".strip()
        # 產生附件（離線測試允許 .txt）
        out_path = Path("data/output")
        out_path.mkdir(parents=True, exist_ok=True)
        att_name = "quote.pdf"
        if simulate == "pdf":
            out["warnings"].append("simulated_pdf_failure")
            att_name = "quote.txt"
        out["attachments"] = [str(out_path / att_name)]
    elif action == "sales_inquiry":
        out["subject"] = f"[詢價] {subject or ''}".strip()
    elif action == "complaint":
        out["subject"] = f"{prefix} {subject or ''}".strip()
        out["meta"].update(_complaint_meta(subject + " " + (payload.get("body") or "")))
    else:
        out["subject"] = f"{prefix} {subject or ''}".strip()
        if action == "reply_faq" and not risks_all:
            out["meta"].setdefault("priority", "P3")

    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_action_handler.py")
    p.add_argument("--json", dest="json_in", help="input json path")
    p.add_argument("--input", dest="inp")
    p.add_argument("--output", "--out", dest="out")
    p.add_argument("--dry-run", dest="dry", action="store_true")
    p.add_argument("--simulate-failure", nargs="?", const="pdf", dest="simulate")
    p.add_argument("--whitelist", action="store_true")
    p.add_argument("extra", nargs="*")
    ns = p.parse_args(argv)

    # 讀取輸入
    raw = None
    if ns.json_in or ns.inp:
        path = ns.json_in or ns.inp
        raw = Path(path).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    try:
        payload = json.loads(raw or "{}")
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        return 2

    whitelist = ns.whitelist or ("whitelist" in (ns.extra or []))
    out = _apply_policy(payload, dry=ns.dry, simulate=ns.simulate, whitelist=whitelist)

    s = json.dumps(out, ensure_ascii=False)
    if ns.out:
        Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.out).write_text(s, encoding="utf-8")
    print(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
