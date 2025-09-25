from __future__ import annotations

import datetime
import os
import pathlib
import re
from typing import Any, Dict

# 固定輸出到專案內的 quotes/ 目錄
QUOTES_DIR = pathlib.Path(os.environ.get("QUOTES_DIR", "quotes"))
QUOTES_DIR.mkdir(parents=True, exist_ok=True)


def _safe_stem(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", name or "")
    s = re.sub(r"_+", "_", s).strip("._")
    return s or "quote"


def _pick(subject: str, body: str) -> str:
    text = f"{subject} {body}"

    def has(*ks):
        return any(k in text for k in ks)

    if has("整合", "API", "ERP", "LINE"):
        return "企業"
    if has("自動分類", "自動化", "排程"):
        return "專業"
    if has("報價", "價格"):
        return "基礎"
    if ("其他詢問" in subject) or ("功能" in body):
        return "企業"
    return "基礎"


def choose_package(*args, **kwargs) -> Dict[str, Any]:
    # 支援舊介面: choose_package(subject, body)
    # 也支援新介面: choose_package({"subject":..., "body":...}) 或 kwargs
    if len(args) == 1 and isinstance(args[0], dict):
        subject = str(args[0].get("subject", ""))
        body = str(args[0].get("body", ""))
    elif kwargs:
        subject = str(kwargs.get("subject", ""))
        body = str(kwargs.get("body", ""))
    else:
        subject = str(args[0]) if len(args) >= 1 else ""
        body = str(args[1]) if len(args) >= 2 else ""
    return {"package": _pick(subject, body), "subject": subject, "content": body}


def generate_pdf_quote(package: str, client_name: str) -> str:
    # 產出最小合法 PDF；副檔名必為 .pdf
    safe = _safe_stem((client_name or "").replace("@", "_").replace(".", "_"))
    pdf_path = QUOTES_DIR / f"{safe}.pdf"
    now = datetime.datetime.utcnow().isoformat()
    payload = (
        "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        "1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        "2 0 obj\n<< /Producer (smart-mail-agent) /CreationDate ("
        + now
        + ") /Title (Quote) /Subject ("
        + str(package)
        + ") >>\nendobj\n"
        "xref\n0 3\n0000000000 65535 f \n0000000015 00000 n \n0000000060 00000 n \n"
        "trailer\n<< /Root 1 0 R /Info 2 0 R >>\nstartxref\n120\n%%EOF\n"
    )
    pdf_path.write_bytes(payload.encode("latin-1", errors="ignore"))
    return str(pdf_path)
