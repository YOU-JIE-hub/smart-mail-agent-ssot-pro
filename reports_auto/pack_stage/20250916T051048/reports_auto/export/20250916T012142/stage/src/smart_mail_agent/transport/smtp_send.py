from __future__ import annotations

import email
import os
import smtplib
from datetime import datetime
from typing import Any

from smart_mail_agent.utils.config import paths


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S")


def send_smtp(mime_bytes: bytes, cfg: dict | None = None) -> dict[str, Any]:
    p = paths()
    cfg = cfg or {}
    host = cfg.get("host") or os.getenv("SMTP_HOST")
    port = int(cfg.get("port") or os.getenv("SMTP_PORT") or 465)
    user = cfg.get("user") or os.getenv("SMTP_USER")
    pwd = cfg.get("pass") or os.getenv("SMTP_PASS")
    use_ssl = bool(cfg.get("ssl", True) if "ssl" in cfg else (os.getenv("SMTP_SSL", "1") == "1"))

    ts = _ts()
    out_eml = p.outbox / f"mail_{ts}.eml"
    out_eml.write_bytes(mime_bytes)

    if os.getenv("SEND_NOW") != "1":
        return {"ok": True, "message_id": None, "eml": str(out_eml), "ts": ts, "sent": False}

    try:
        if use_ssl:
            s = smtplib.SMTP_SSL(host=host, port=port, timeout=20)
        else:
            s = smtplib.SMTP(host=host, port=port, timeout=20)
            s.starttls()
        if user and pwd:
            s.login(user, pwd)
        msg = email.message_from_bytes(mime_bytes)
        s.send_message(msg)
        s.quit()
        sent_dir = p.outbox / "sent"
        sent_dir.mkdir(exist_ok=True)
        out_eml.rename(sent_dir / out_eml.name)
        return {
            "ok": True,
            "message_id": msg.get("Message-Id"),
            "eml": str(sent_dir / out_eml.name),
            "ts": ts,
            "sent": True,
        }
    except Exception as e:  # noqa: BLE001
        retry_dir = p.outbox / "retry"
        retry_dir.mkdir(exist_ok=True)
        (retry_dir / out_eml.name).write_bytes(mime_bytes)
        return {"ok": False, "error": str(e), "eml": str(retry_dir / out_eml.name), "ts": ts, "sent": False}
