from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import os, smtplib, ssl, time, email, imaplib
from email.message import EmailMessage

def _ensure_dir(p: Path) -> Path:
    p = Path(p); p.mkdir(parents=True, exist_ok=True); return p

def send_email(
    outbox: Path,
    to_addr: str,
    subject: str,
    body: str,
    attachments: Optional[List[Path]] = None,
    dry_run: bool = False,
    db_log: Optional[Callable[[str, tuple], None]] = None,
) -> Dict[str, Any]:
    """
    通用寄信工具：
      1) 一律先把 .eml 備份到 outbox（可供審計）
      2) OFFLINE=1 或 dry_run=True 或缺 SMTP 參數 => 僅落地 .eml（不打外部 SMTP）
      3) 若提供 SMTP 參數 => 嘗試送出（失敗也會返回 ok=False 並保留 .eml）
    讀取環境變數：
      SMA_SMTP_HOST, SMA_SMTP_PORT, SMA_SMTP_STARTTLS, SMA_SMTP_USER, SMA_SMTP_PASS, SMA_SMTP_FROM
    """
    outbox = _ensure_dir(Path(outbox))
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["From"] = os.getenv("SMA_SMTP_FROM", os.getenv("SMA_SMTP_USER", "no-reply@example.com"))
    msg["Subject"] = subject
    msg.set_content(body or "")

    # 附件：檔案存在就附上，否則附上文字描述，避免測試 flakiness
    for p in attachments or []:
        p = Path(p)
        if p.exists():
            data = p.read_bytes()
            msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=p.name)
        else:
            # fallback 純文字附件（以內嵌段落紀錄）
            msg.add_attachment(f"[missing attachment note] {p}".encode("utf-8"),
                               maintype="text", subtype="plain", filename=p.name+".txt")

    # 一律先落地 .eml 以利審計
    ts = time.strftime("%Y%m%dT%H%M%S")
    eml_path = outbox / f"{ts}_{subject.replace(' ','_')}.eml"
    eml_path.write_bytes(msg.as_bytes())

    # 寫 audit（只要 caller 有提供 db_log）
    detail = {"action":"send_email","to":to_addr,"subject":subject,"eml":str(eml_path),"dry_run":bool(dry_run)}
    if db_log:
        try:
            db_log("INSERT INTO audits VALUES (?,?,?,?)", (time.time(), "send_email", "mail", json_dumps(detail)))
        except Exception:
            pass

    # 離線或未配置 SMTP：只寫檔
    if os.getenv("OFFLINE") == "1" or dry_run:
        return {"ok": True, "via": "file", "path": str(eml_path)}

    host = os.getenv("SMA_SMTP_HOST"); port = int(os.getenv("SMA_SMTP_PORT", "0") or 0)
    user = os.getenv("SMA_SMTP_USER"); pwd = os.getenv("SMA_SMTP_PASS")
    starttls = os.getenv("SMA_SMTP_STARTTLS", "0") in ("1","true","TRUE","yes","YES")

    if not host or not port:
        return {"ok": True, "via": "file", "path": str(eml_path)}

    try:
        smtp = smtplib.SMTP(host, port, timeout=10)
        smtp.ehlo()
        if starttls:
            ctx = ssl.create_default_context()
            smtp.starttls(context=ctx)
            smtp.ehlo()
        if user and pwd:
            smtp.login(user, pwd)
        smtp.send_message(msg)
        smtp.quit()
        return {"ok": True, "via": "smtp", "path": str(eml_path)}
    except Exception as err:
        return {"ok": False, "via": "smtp", "path": str(eml_path), "error": str(err)}

def json_dumps(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "{}"

def receive_imap(host: str, user: str, password: str, folder: str = "INBOX", limit: int = 10, timeout: int = 10):
    """
    可選 IMAP 收信：若 OFFLINE=1 直接回空陣列；否則連線取回主旨清單。
    測試可 monkeypatch mail_io.imaplib.IMAP4_SSL 來 stub。
    """
    if os.getenv("OFFLINE") == "1":
        return []
    M = imaplib.IMAP4_SSL(host, timeout=timeout)
    try:
        M.login(user, password)
        M.select(folder)
        typ, data = M.search(None, "ALL")
        ids = (data[0] or b"").split()
        if limit:
            ids = ids[-limit:]
        out: List[Dict[str, Any]] = []
        for i in ids:
            typ2, raw = M.fetch(i, "(RFC822)")
            if typ2 != "OK" or not raw or not raw[0] or raw[0][1] is None:
                continue
            msg = email.message_from_bytes(raw[0][1])
            out.append({"subject": msg.get("Subject","")})
        return out
    finally:
        try: M.logout()
        except Exception: pass
