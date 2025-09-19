#!/usr/bin/env python3
import argparse, os, ssl, smtplib, pathlib, fnmatch, mimetypes, email.utils, sqlite3, json, time, sys, traceback
from email.message import EmailMessage
from email import policy

# ------------ helpers ------------
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")

def whitelist_ok(to_addr: str, wl: str) -> bool:
    if not wl: return True
    pats = [x.strip() for x in wl.split(",") if x.strip()]
    return any(fnmatch.fnmatch(to_addr, p) for p in pats)

def latest_run_dir(base="reports_auto/e2e_mail"):
    p = pathlib.Path(base)
    if not p.exists(): return None
    runs = sorted([x for x in p.iterdir() if x.is_dir()], key=lambda x: x.name, reverse=True)
    return runs[0] if runs else None

def read_outbox_txt(txt: pathlib.Path):
    """Read minimal RFC-ish txt: Subject: (opt), To: (ignored), remain=body"""
    subject, body_lines = None, []
    for i, line in enumerate(txt.read_text(encoding="utf-8", errors="ignore").splitlines()):
        low = line.lower()
        if i < 50 and low.startswith("subject:"):
            subject = line.split(":",1)[1].strip()
        elif i < 50 and low.startswith("to:"):
            continue
        else:
            body_lines.append(line)
    if not subject: subject = f"[SmartMail] Case {txt.stem}"
    body = "\n".join(body_lines).strip() or f"Auto-reply for case {txt.stem}."
    return subject, body

def guess_text_kind(path: pathlib.Path):
    mt, _ = mimetypes.guess_type(str(path))
    if mt:
        m, s = mt.split("/",1)
        return m, s
    # fallbacks
    ext = path.suffix.lower()
    if ext in (".txt",".md"): return "text","plain"
    if ext in (".html",".htm"): return "text","html"
    if ext in (".json",): return "application","json"
    return "application","octet-stream"

def safe_add_attachment(msg: EmailMessage, path: pathlib.Path):
    mtype, subtype = guess_text_kind(path)
    if mtype == "text":
        data = path.read_text(encoding="utf-8", errors="ignore")
        msg.add_attachment(data, maintype=mtype, subtype=subtype, filename=path.name, charset="utf-8")
    else:
        data = path.read_bytes()
        msg.add_attachment(data, maintype=mtype, subtype=subtype, filename=path.name)

def load_action_index(db_path: pathlib.Path, run_ts: str):
    idx = {}
    if not db_path.exists(): return idx
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT case_id, COALESCE(action_type, action) AS t, payload_ref
        FROM actions WHERE run_ts=?
        """, (run_ts,))
        for case_id, t, ref in cur.fetchall():
            d = idx.setdefault(case_id, {})
            d.setdefault(t, []).append(ref)
    finally:
        conn.close()
    return idx

# ------------ compose & send ------------
def compose_message(case_id, to_addr, subject, body, run_dir: pathlib.Path, action_idx: dict):
    msg = EmailMessage(policy=policy.SMTP)
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMA_SMTP_USER") or os.getenv("SMTP_USER") or "noreply@example.com"
    msg["To"] = to_addr
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid()

    # plain + html
    msg.set_content(body, subtype="plain", charset="utf-8")
    html = "<html><meta charset='utf-8'><body><pre style='white-space:pre-wrap'>" + \
           (body.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")) + \
           "</pre></body></html>"
    msg.add_alternative(html, subtype="html", charset="utf-8")

    # attach by intent/action
    intent = "-"
    aid = action_idx.get(case_id, {})
    # GenerateQuote → attach .html
    for ref in aid.get("GenerateQuote", []):
        p = run_dir.joinpath(ref) if not str(ref).startswith("/") else pathlib.Path(ref)
        if p.exists(): safe_add_attachment(msg, p); intent = "報價"
    # GenerateDiff → attach .json
    for ref in aid.get("GenerateDiff", []):
        p = run_dir.joinpath(ref) if not str(ref).startswith("/") else pathlib.Path(ref)
        if p.exists(): safe_add_attachment(msg, p); intent = "資料異動"
    # CreateTicket → subject + attach json
    for ref in aid.get("CreateTicket", []):
        p = run_dir.joinpath(ref) if not str(ref).startswith("/") else pathlib.Path(ref)
        if p.exists():
            try:
                j = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                tid = j.get("ticket_id") or j.get("id") or ""
                if tid:
                    msg.replace_header("Subject", f"[Ticket:{tid}] {subject}")
            except Exception:
                pass
            safe_add_attachment(msg, p)
            intent = "投訴" if intent == "-" else intent
    # FAQReply → inline append
    for ref in aid.get("FAQReply", []):
        p = run_dir.joinpath(ref) if not str(ref).startswith("/") else pathlib.Path(ref)
        if p.exists():
            faq = p.read_text(encoding="utf-8", errors="ignore").strip()
            if faq:
                msg.set_content(body + "\n\n--- FAQ Reply ---\n" + faq, subtype="plain", charset="utf-8")
                html2 = "<html><meta charset='utf-8'><body><pre style='white-space:pre-wrap'>" + \
                        ((body + "\n\n--- FAQ Reply ---\n" + faq).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")) + \
                        "</pre></body></html>"
                msg.add_alternative(html2, subtype="html", charset="utf-8")
                if intent == "-": intent = "規則詢問"
    return msg, intent

def main():
    ap = argparse.ArgumentParser(description="Send outbox emails with intent-based attachments.")
    ap.add_argument("--run-dir", default="", help="run dir under reports_auto/e2e_mail")
    ap.add_argument("--to", required=True, help="recipient email")
    ap.add_argument("--force", action="store_true", help="re-send even if .eml exists")
    args = ap.parse_args()

    # env / smtp
    host = os.getenv("SMA_SMTP_HOST", os.getenv("SMTP_HOST", "smtp.gmail.com"))
    port = int(os.getenv("SMA_SMTP_PORT", os.getenv("SMTP_PORT", "587")))
    user = os.getenv("SMA_SMTP_USER", os.getenv("SMTP_USER", ""))
    pwd  = os.getenv("SMA_SMTP_PASS", os.getenv("SMTP_PASS", ""))
    tls  = os.getenv("SMA_SMTP_TLS", os.getenv("SMTP_TLS", "starttls"))
    wl   = os.getenv("SMA_EMAIL_WHITELIST","")
    if not whitelist_ok(args.to, wl):
        print(f"[DENY] {args.to} not in whitelist={wl}", file=sys.stderr); sys.exit(2)

    run_dir = pathlib.Path(args.run_dir) if args.run_dir else latest_run_dir()
    if not run_dir or not run_dir.exists():
        print("[ERR] run-dir not found. Please generate a run first.", file=sys.stderr); sys.exit(3)
    run_ts = run_dir.name
    outbox = run_dir / "rpa_out" / "email_outbox"
    sent_dir = run_dir / "rpa_out" / "email_sent"
    sent_dir.mkdir(parents=True, exist_ok=True)

    action_idx = load_action_index(pathlib.Path("db/sma.sqlite"), run_ts)

    print(f"[SMTP] {host}:{port} as {user} (TLS={tls})  whitelist={wl or '[none]'}")
    sent = skipped = failed = 0
    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as srv:
        srv.ehlo()
        if tls.lower() == "starttls": srv.starttls(context=ctx)
        if user: srv.login(user, pwd)

        for txt in sorted(outbox.glob("*.txt")):
            case_id = txt.stem
            eml_path = sent_dir / f"{case_id}.eml"
            if eml_path.exists() and not args.force:
                print(f"[SKIP] {case_id} already sent (.eml exists)")
                skipped += 1
                continue

            subject, body = read_outbox_txt(txt)
            msg, intent = compose_message(case_id, args.to, subject, body, run_dir, action_idx)

            try:
                srv.send_message(msg)
                with open(eml_path, "wb") as f: f.write(bytes(msg))
                sent += 1
                print(f"[OK] sent {eml_path.name} → {args.to}  (intent={intent})")
            except Exception as e:
                failed += 1
                print(f"[FAIL] {case_id}: {e}", file=sys.stderr)
                traceback.print_exc()

    # best-effort DB update
    try:
        conn = sqlite3.connect("db/sma.sqlite")
        cur = conn.cursor()
        cur.execute("UPDATE actions SET status='succeeded', updated_at=?, ended_at=?, payload_ref=REPLACE(payload_ref,'email_outbox','email_sent') WHERE run_ts=? AND COALESCE(action_type,action)='SendEmail'", (now(), now(), run_ts))
        conn.commit(); conn.close()
    except Exception:
        pass

    print(f"[DONE] run={run_ts}  sent={sent}, skipped={skipped}, failed={failed}")
    sys.exit(0 if failed==0 else 1)

if __name__ == "__main__":
    main()
