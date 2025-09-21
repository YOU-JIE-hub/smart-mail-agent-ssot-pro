#!/usr/bin/env python3
import os, re, smtplib, ssl, sys
from pathlib import Path
from email import message_from_string, message_from_bytes, policy
from email.utils import getaddresses
from fnmatch import fnmatch

def env(name, default=None, required=False):
    v=os.environ.get(name, default)
    if required and not v:
        print(f"[FATAL] missing env: {name}"); sys.exit(2)
    return v

def load_msg(p: Path):
    raw = p.read_bytes()
    try:
        try: msg = message_from_bytes(raw, policy=policy.SMTP)
        except Exception: msg = message_from_string(raw.decode('utf-8', 'ignore'), policy=policy.SMTP)
        return msg, raw
    except Exception as e:
        print(f"[SKIP] bad email file: {p.name} ({e})")
        return None, None

def match_any(addr:str, patterns):
    a=addr.lower().strip()
    return any(fnmatch(a, pat.lower().strip()) for pat in patterns if pat.strip())

def main():
    if os.environ.get("SMA_SMTP_MODE","outbox").lower()!="smtp":
        print("[INFO] SMA_SMTP_MODE!=smtp → 只做掃描，不送信"); return 0

    host = env("SMA_SMTP_HOST","smtp.gmail.com")
    port = int(env("SMA_SMTP_PORT","587"))
    user = env("SMA_SMTP_USER", required=True)
    pwd  = env("SMA_SMTP_PASS", required=True)
    tls  = env("SMA_SMTP_TLS","starttls").lower()

    wl = env("SMA_EMAIL_WHITELIST","").replace(";",",").split(",")
    if not any(p.strip() for p in wl):
        print("[WARN] 沒設 SMA_EMAIL_WHITELIST，將拒絕所有收件人以避免誤寄")
    run_dir = Path(sys.argv[1]) if len(sys.argv)>1 else Path(sorted([str(p) for p in Path("reports_auto/e2e_mail").glob("*")])[-1])
    outbox = run_dir/"rpa_out"/"email_outbox"
    sent   = run_dir/"rpa_out"/"email_sent"
    sent.mkdir(parents=True, exist_ok=True)
    files  = sorted(outbox.glob("*.txt"))
    if not files:
        print(f"[INFO] no outbox mails in {outbox}"); return 0

    print(f"[INFO] try sending {len(files)} mails via {host}:{port} as {user} (TLS={tls})")

    if tls=="starttls":
        server = smtplib.SMTP(host, port, timeout=30); server.ehlo(); server.starttls(context=ssl.create_default_context()); server.login(user, pwd)
    elif tls in ("tls","ssl"):
        server = smtplib.SMTP_SSL(host, port, timeout=30); server.login(user, pwd)
    else:
        server = smtplib.SMTP(host, port, timeout=30); server.login(user, pwd)

    sent_ok=0; skipped=0
    try:
        for f in files:
            msg, raw = load_msg(f)
            if not msg: 
                skipped+=1; continue
            tos = [a for n,a in getaddresses(msg.get_all('To', []))]
            ccs = [a for n,a in getaddresses(msg.get_all('Cc', []))]
            bccs= [a for n,a in getaddresses(msg.get_all('Bcc', []))]
            rcpts = [a for a in (tos+ccs+bccs) if a]
            rcpts_allowed = [a for a in rcpts if match_any(a, wl)]
            if not rcpts_allowed:
                print(f"[SKIP] {f.name} no recipients in whitelist → {wl}")
                skipped+=1; continue
            try:
                server.sendmail(user, rcpts_allowed, raw)
                (sent/f.with_suffix(".eml").name).write_bytes(raw)
                print(f"[OK] sent {f.name} → {','.join(rcpts_allowed)}")
                sent_ok+=1
            except Exception as e:
                print(f"[ERR] send failed {f.name}: {e}")
    finally:
        try: server.quit()
        except: pass
    print(f"[DONE] sent_ok={sent_ok}, skipped={skipped}, saved_to={sent}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
