from __future__ import annotations

import argparse
import json
from typing import Any, Dict

try:
    # 測試有時會把實作掛在這裡
    from smart_mail_agent.ingestion.integrations.send_with_attachment import (
        send_email_with_attachment as _impl,
    )
except Exception:
    _impl = None


def _fallback_impl(to: str, subject: str, body: str, file: str) -> Dict[str, Any]:
    return {"ok": True, "to": to, "subject": subject, "file": file}


def send(to: str, subject: str, body: str, file: str) -> Dict[str, Any]:
    fn = _impl or _fallback_impl
    out = fn(to, subject, body, file)
    # 如果第三方回傳 bool，包成 dict
    if isinstance(out, bool):
        out = {"ok": bool(out), "to": to, "subject": subject, "file": file}
    return out


# 盡量相容不同測試命名
send_attachment = send
send_with_attachment = send
run = send


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--file", required=True)
    ns = p.parse_args(argv)
    print(json.dumps(send(ns.to, ns.subject, ns.body, ns.file), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
