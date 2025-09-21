from __future__ import annotations
import os, json, datetime as _dt
from pathlib import Path
__all__ = ["execute"]
def execute(payload: dict, out_dir: str = "reports_auto/e2e_mail/_outbox", email_mode: str = "file") -> dict:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    mail_id = payload.get("id") or payload.get("mail_id") or "msg"
    action = payload.get("action","noop")
    fp = Path(out_dir) / f"payload_{mail_id}_{action}.json"
    payload = dict(payload)
    payload.setdefault("audit", {})["executed_at"] = _dt.datetime.utcnow().isoformat()+"Z"
    with fp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return {"path": str(fp), "ok": True}
