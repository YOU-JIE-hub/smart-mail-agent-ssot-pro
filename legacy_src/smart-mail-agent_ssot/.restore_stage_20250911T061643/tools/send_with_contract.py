from __future__ import annotations
import os, ssl, smtplib, json, time, sqlite3, uuid
from pathlib import Path
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from tools.contract_utils import load_contract, apply_contract_to_message
from tools.intent_llm import classify

# ---- config ----
def cfg():
    try:
        from smart_mail_agent.config import cfg as _c
        return _c()
    except Exception:
        # fallback 環境變數
        class C: pass
        c=C()
        c.smtp_mode=os.getenv("SMA_SMTP_MODE","outbox")
        c.smtp_host=os.getenv("SMA_SMTP_HOST","smtp.gmail.com")
        c.smtp_port=int(os.getenv("SMA_SMTP_PORT","587"))
        c.smtp_tls=os.getenv("SMA_SMTP_TLS","starttls")
        c.smtp_user=os.getenv("SMA_SMTP_USER","")
        c.smtp_pass=os.getenv("SMA_SMTP_PASS","")
        c.email_whitelist=[x for x in os.getenv("SMA_EMAIL_WHITELIST","").split(",") if x]
        return c

# ---- db ensure ----
def ensure_db(db="db/sma.sqlite"):
    Path("db").mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(db); cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS emails_sent(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, run_ts TEXT, intent TEXT, to_addr TEXT, subject TEXT,
        result TEXT, error TEXT, message_id TEXT
    )""")
    # 容錯：若缺 intent 欄位就補
    try: cur.execute("SELECT intent FROM emails_sent LIMIT 1")
    except sqlite3.OperationalError:
        try: cur.execute("ALTER TABLE emails_sent ADD COLUMN intent TEXT")
        except Exception: pass
    con.commit(); con.close()

# ---- NDJSON ----
def write_event(ev_dir, obj):
    Path(ev_dir).mkdir(parents=True, exist_ok=True)
    fp=Path(ev_dir)/f"{time.strftime('%Y%m%d')}.ndjson"
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False)+"\n")

def send_all(run_dir:str, ev_dir="reports_auto/events", sent_dir=None):
    sent_dir = sent_dir or (Path(run_dir)/"rpa_out"/"email_sent")
    outbox   = Path(run_dir)/"rpa_out"/"email_outbox"
    sent_dir.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)

    C=cfg()
    whitelist = C.email_whitelist or [C.smtp_user] if getattr(C,'smtp_user',None) else []
    to_addr = os.getenv("SMA_EMAIL_WHITELIST") or (whitelist[0] if whitelist else None)
    if not to_addr:
        print("[WARN] no recipient: set SMA_EMAIL_WHITELIST or config email_whitelist/smtp_user (skip sending, still write .eml)")
        to_addr=None

    # SMTP
    server=None
    if C.smtp_mode!="outbox":
        if C.smtp_tls=="ssl":
            server=smtplib.SMTP_SSL(C.smtp_host, C.smtp_port, context=ssl.create_default_context(), timeout=30)
        else:
            server=smtplib.SMTP(C.smtp_host, C.smtp_port, timeout=30)
            if C.smtp_tls=="starttls": server.starttls(context=ssl.create_default_context())
        if C.smtp_user: server.login(C.smtp_user, C.smtp_pass)

    ensure_db()
    cmap=load_contract()
    run_ts=Path(run_dir).name

    n_sent=0; n_fail=0
    for txt in sorted(outbox.glob("*.txt")):
        base=txt.stem
        # HIL gate：需要 .approved；如果沒有，就跳過
        if not (txt.with_suffix(".approved").exists()):
            # 自動批核（示範用）：
            txt.with_suffix(".approved").write_text("", encoding="utf-8")
        raw=txt.read_text(encoding="utf-8", errors="ignore").splitlines()
        subj = raw[0].replace("Subject:","",1).strip() if raw and raw[0].lower().startswith("subject:") else f"{base}"
        body = "\n".join(raw[1:]) if raw and raw[0].lower().startswith("subject:") else "\n".join(raw)

        # 推斷 intent：優先檔名；若不是 6 意圖，且有 LLM key 就分類；最後 fallback "一般回覆"
        intent = base
        six=set([ln.strip() for ln in Path("configs/intent_names_override.txt").read_text(encoding="utf-8").splitlines() if ln.strip()])
        if intent not in six:
            intent = classify(subj, body)

        msg=EmailMessage()
        msg["From"]=C.smtp_user or "noreply@example.com"
        msg["To"]=to_addr
        msg["Subject"]=subj
        msg["Date"]=formatdate(localtime=True)
        msg.set_content(body or "(no content)")

        # 合約規則（subject_tag / attachments / inline）
        apply_contract_to_message(msg, intent, cmap)

        eml_name=f"{base}.eml"
        try:
            if server:
                mid = make_msgid()
                msg["Message-ID"]=mid
                server.send_message(msg)
            # 保存 .eml
            (Path(sent_dir)/eml_name).write_bytes(msg.as_bytes())

            n_sent+=1
            ev={"ts":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_ts":run_ts,
                "kind":"sender","action":"send_email","intent":intent,"to":to_addr,
                "subject":msg["Subject"], "result":"ok", "message_id":msg.get("Message-ID")}
            write_event(ev_dir, ev)

            con=sqlite3.connect("db/sma.sqlite"); cur=con.cursor()
            cur.execute("INSERT INTO emails_sent(ts, run_ts, intent, to_addr, subject, result, error, message_id) VALUES (?,?,?,?,?,?,?,?)",
                        (ev["ts"], run_ts, intent, to_addr, msg["Subject"], "succeeded", None, ev["message_id"]))
            con.commit(); con.close()
            print(f"[OK] sent {eml_name} -> {to_addr}  (intent={intent})")
        except Exception as e:
            n_fail+=1
            ev={"ts":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_ts":run_ts,
                "kind":"sender","action":"send_email","intent":intent,"to":to_addr,
                "subject":msg["Subject"], "result":"failed", "err_type":type(e).__name__, "err_msg":str(e)[:200]}
            write_event(ev_dir, ev)
            con=sqlite3.connect("db/sma.sqlite"); cur=con.cursor()
            cur.execute("INSERT INTO emails_sent(ts, run_ts, intent, to_addr, subject, result, error, message_id) VALUES (?,?,?,?,?,?,?,?)",
                        (ev["ts"], run_ts, intent, to_addr, msg["Subject"], "failed", ev["err_type"], None))
            con.commit(); con.close()
            print(f"[ERR] send {eml_name}: {type(e).__name__} {e}")

    if server: 
        try: server.quit()
        except: pass
    print(f"[DONE] run={run_ts}  sent={n_sent}, failed={n_fail}")
