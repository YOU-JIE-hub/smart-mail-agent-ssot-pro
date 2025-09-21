#!/usr/bin/env python3
import os, smtplib, json, time
from email.mime.text import MIMEText
from pathlib import Path

class FileTransport:
    def __init__(self, outbox_dir: Path):
        self.out = Path(outbox_dir); self.out.mkdir(parents=True, exist_ok=True)
    def send(self, to_addr, subject, body, run_id, mail_id, action):
        ts=time.strftime("%Y%m%d-%H%M%S")
        meta={"to":to_addr,"subject":subject,"run_id":run_id,"mail_id":mail_id,"action":action,"ts":ts}
        fn=f"{ts}_{to_addr.replace('@','_')}_{action}.txt"
        (self.out/fn).write_text(subject + "\n\n" + body + "\n\n--\n" + json.dumps(meta,ensure_ascii=False), encoding="utf-8")
        return str(self.out/fn)

class SMTPTransport:
    def __init__(self):
        self.host=os.getenv("SMTP_HOST"); self.port=int(os.getenv("SMTP_PORT","587"))
        self.user=os.getenv("SMTP_USER"); self.pw=os.getenv("SMTP_PASS")
        self.sender=os.getenv("SMTP_SENDER","noreply@example.com")
    def send(self, to_addr, subject, body, run_id, mail_id, action):
        if not (self.host and self.user and self.pw):
            return ""
        msg=MIMEText(body, _charset="utf-8"); msg["Subject"]=subject; msg["From"]=self.sender; msg["To"]=to_addr
        with smtplib.SMTP(self.host, self.port) as s:
            s.starttls(); s.login(self.user, self.pw); s.sendmail(self.sender, [to_addr], msg.as_string())
        return f"smtp://{to_addr}/{action}"
