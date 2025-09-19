import email
import pathlib
from datetime import datetime
from email import policy
from typing import Any


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def load_dir(path: str) -> list[dict[str, Any]]:
    p = pathlib.Path(path)
    if not p.exists():
        return []
    items = []
    for f in sorted(p.glob("*")):
        if f.suffix.lower() in {".txt"} and f.is_file():
            body = f.read_text(encoding="utf-8", errors="ignore")
            items.append({"id": f.stem, "subject": None, "sender": None, "body": body, "ts": _now()})
        elif f.suffix.lower() in {".eml"} and f.is_file():
            msg = email.message_from_bytes(f.read_bytes(), policy=policy.default)
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content()
                        break
            else:
                body = msg.get_content()
            items.append(
                {
                    "id": f.stem,
                    "subject": msg.get("Subject"),
                    "sender": msg.get("From"),
                    "body": body or "",
                    "ts": _now(),
                }
            )
    return items
