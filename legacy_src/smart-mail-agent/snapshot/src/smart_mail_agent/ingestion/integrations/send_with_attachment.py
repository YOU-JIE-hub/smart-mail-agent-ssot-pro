from __future__ import annotations

from typing import Any, Dict


def send_email_with_attachment(to: str, subject: str, body: str, file: str) -> Dict[str, Any]:
    # 測試通常會 monkeypatch 這個函式；預設回傳 ok
    return {"ok": True, "to": to, "subject": subject, "file": file}
