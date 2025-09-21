from __future__ import annotations
import os, sys, smtplib, argparse
from email.message import EmailMessage
from pathlib import Path
from smart_mail_agent.observability.ndjson_v1 import NDJSONLogger

def read_outbox_txt(p: Path)->tuple[str,str]:
    text = p.read_text(encoding="utf-8", errors="ignore")
    subject="mail"; lines=text.splitlines()
    for i,ln in enumerate(lines):
        if ln.lower().startswith("subject:"):
            subject=(ln.split(":",1)[1].strip() or "mail")[:120]
            body="\n".join(lines[i+1:]) if i+1<len(lines) else ""
            return subject, body
    return subject, text

def build_message(from_addr:str, to_addr:str, subject:str, body:str)->EmailMessage:
    msg=EmailMessage()
    msg["From"]=from_addr; msg["To"]=to_addr; msg["Subject"]=subject
    msg.set_content(body)
    msg.add_alternative(f"<html><body><pre>{body}</pre></body></html>", subtype="html")
    return msg

def save_eml(msg:EmailMessage, path:Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msg.as_bytes())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--force", action="store_true")
    a=ap.parse_args()

    rd=Path(a.run_dir)
    outbox=rd/"rpa_out"/"email_outbox"
    sent_dir=rd/"rpa_out"/"email_sent"
    blocked=rd/"rpa_out"/"email_blocked"
    outbox.mkdir(parents=True, exist_ok=True); sent_dir.mkdir(parents=True, exist_ok=True); blocked.mkdir(parents=True, exist_ok=True)

    # 事件紀錄器（每個 run_ts 一個 NDJSON）
    events_path = Path(f"reports_auto/events/{rd.name}.ndjson")
    logger = NDJSONLogger(str(events_path))

    # SMTP 設定與白名單
    mode=os.getenv("SMA_SMTP_MODE","smtp")
    host=os.getenv("SMA_SMTP_HOST","smtp.gmail.com")
    port=int(os.getenv("SMA_SMTP_PORT","587"))
    tls=os.getenv("SMA_SMTP_TLS","starttls")
    user=os.getenv("SMA_SMTP_USER","")
    pwd =os.getenv("SMA_SMTP_PASS","")
    whitelist=[x.strip().lower() for x in os.getenv("SMA_EMAIL_WHITELIST","").split(",") if x.strip()]
    cap=int(os.getenv("SMA_ACTION_CAP_SEND_EMAIL","200") or "200")
    print(f"[SMTP] {host}:{port} as {user} (TLS={tls})  whitelist={','.join(whitelist) if whitelist else '(none)'}")

    # 白名單檢查
    to=a.to.strip().lower()
    if whitelist and to not in whitelist:
        print(f"[DENY] {to} not in whitelist={','.join(whitelist)}")
        logger.write(action="send_email", result="deny_whitelist", idem="*", intent=None, err_msg=to)
        return 0

    # 是否 outbox-only
    outbox_only = (mode!="smtp") or not (user and pwd)

    # 準備 SMTP（若需要）
    srv=None
    if not outbox_only:
        srv=smtplib.SMTP(host, port, timeout=20)
        if tls=="starttls":
            srv.starttls()
        if user and pwd:
            srv.login(user, pwd)

    sent=skipped=failed=0
    count=0
    for txt in sorted(outbox.glob("*.txt")):
        count+=1
        if count>cap: break
        idem = txt.stem
        subject, body = read_outbox_txt(txt)
        msg = build_message(user or "noreply@example.com", to, subject, body)
        eml_path = sent_dir / f"{idem}.eml"
        if eml_path.exists() and not a.force:
            print(f"[SKIP] {eml_path.name} already exists")
            skipped+=1
            logger.write(action="send_email", result="skip", idem=idem, intent=None)
            continue
        try:
            if outbox_only:
                save_eml(msg, eml_path)
                print(f"[OUTBOX-ONLY] saved {eml_path.name} → {to}")
                sent+=1
                logger.write(action="send_email", result="outbox_only", idem=idem, intent=None)
            else:
                srv.send_message(msg)
                save_eml(msg, eml_path)
                print(f"[OK] sent {eml_path.name} → {to}  (intent=-)")
                sent+=1
                logger.write(action="send_email", result="ok", idem=idem, intent=None)
        except Exception as e:
            failed+=1
            print(f"[FAIL] {idem}: {e!r}")
            logger.write(action="send_email", result="fail", idem=idem, intent=None,
                         err_type=getattr(e,'__class__',type(e)).__name__, err_msg=str(e))
    if srv: 
        try: srv.quit()
        except Exception: pass
    print(f"[DONE] run={rd.name}  sent={sent}, skipped={skipped}, failed={failed}")

if __name__=="__main__":
    sys.exit(main() or 0)
