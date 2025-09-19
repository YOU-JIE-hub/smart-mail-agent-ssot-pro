from __future__ import annotations
import os, ssl, smtplib, time, mimetypes
from pathlib import Path
from typing import Iterable, Optional, Union, Dict, Any, List
from email.message import EmailMessage
from email.utils import make_msgid, formatdate

SMTP_HOST = os.environ.get("SMTP_HOST") or ""
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "0") or 587
SMTP_USER = os.environ.get("SMTP_USER") or ""
SMTP_PASS = os.environ.get("SMTP_PASS") or ""
SMTP_SENDER = os.environ.get("SMTP_SENDER") or (os.environ.get("SMTP_USER") or "no-reply@example.com")
OUTBOX_DIR = Path(os.environ.get("SMA_OUTBOX_DIR") or "rpa_out/email_outbox")

def _ensure_outbox() -> Path:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    return OUTBOX_DIR

def _as_list(x: Union[str, Iterable[str]]) -> List[str]:
    if isinstance(x, str): return [x]
    return list(x)

def _build_message(sender: str,
                   to_addrs: Union[str, Iterable[str]],
                   subject: str,
                   body_text: str,
                   attachments: Optional[Iterable[Union[str, Path, Dict[str, Any]]]] = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(_as_list(to_addrs))
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body_text)
    for att in (attachments or []):
        if isinstance(att, (str, Path)):
            p = Path(att)
            if not p.exists(): continue
            ctype, _ = mimetypes.guess_type(p.name)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            with open(p, "rb") as f: data = f.read()
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=p.name)
        elif isinstance(att, dict):
            filename = att.get("filename") or "attachment.bin"
            data = att.get("content") or b""
            mime = att.get("mime") or "application/octet-stream"
            maintype, subtype = mime.split("/", 1)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg

def _write_eml(msg: EmailMessage, outbox_dir: Optional[Union[str, Path]] = None, prefix: Optional[str] = None) -> Path:
    outbox = Path(outbox_dir) if outbox_dir else _ensure_outbox()
    ts = time.strftime("%Y%m%dT%H%M%S")
    subj = (msg.get("Subject") or "no_subject").strip().replace("/", "_").replace("\\", "_")
    stem = f"{prefix+'_' if prefix else ''}{ts}_{subj}"
    eml_path = outbox / f"{stem}.eml"
    i = 1
    while eml_path.exists():
        eml_path = outbox / f"{stem}_{i}.eml"; i += 1
    with open(eml_path, "wb") as f: f.write(bytes(msg))
    return eml_path

def send_file_transport(to_addrs: Union[str, Iterable[str]], subject: str, body_text: str,
                        attachments: Optional[Iterable[Union[str, Path, Dict[str, Any]]]] = None,
                        outbox_dir: Optional[Union[str, Path]] = None, prefix: Optional[str] = None) -> Dict[str, Any]:
    try:
        msg = _build_message(SMTP_SENDER, to_addrs, subject, body_text, attachments)
        p = _write_eml(msg, outbox_dir, prefix)
        return {"status":"succeeded","transport":"file","outbox_path":str(p),"message_id":msg["Message-ID"]}
    except Exception as e:
        return {"status":"failed","transport":"file","error":f"{type(e).__name__}: {e}"}

def send_smtp(timeout=None,timeout=None,to_addrs: Union[str, Iterable[str]], subject: str, body_text: str,
              attachments: Optional[Iterable[Union[str, Path, Dict[str, Any]]]] = None,
              timeout: int = 20, always_copy_to_outbox: bool = True) -> Dict[str, Any]:
    if not SMTP_HOST or not SMTP_SENDER:
        res = send_file_transport(to_addrs, subject, body_text, attachments, prefix="downgraded_no_smtp")
        res["status"] = "downgraded"; res["transport"] = "file"; res["error"] = "smtp_not_configured"
        return res
    msg = _build_message(SMTP_SENDER, to_addrs, subject, body_text, attachments)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host=SMTP_HOST, port=SMTP_PORT, timeout=timeout) as server:
            server.ehlo()
            try:
                server.starttls(context=context); server.ehlo()
            except smtplib.SMTPException:
                pass
            if SMTP_USER: server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    except Exception as e:
        res = send_file_transport(to_addrs, subject, body_text, attachments, prefix="downgraded_smtp_fail")
        res["status"] = "downgraded"; res["transport"] = "file"; res["error"] = f"{type(e).__name__}: {e}"
        return res
    out = {"status":"succeeded","transport":"smtp","message_id":msg["Message-ID"]}
    if always_copy_to_outbox:
        p = _write_eml(msg, prefix="smtp_copy"); out["outbox_path"] = str(p)
    return out
