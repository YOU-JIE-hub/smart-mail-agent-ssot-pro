#!/usr/bin/env python3
import argparse, json, os, sqlite3, hashlib, datetime, re, subprocess
from pathlib import Path
from scripts.mail_transport import FileTransport, SMTPTransport

LOG_DIR = Path(os.getenv("SMA_LOG_DIR", "reports_auto/logs")); LOG_DIR.mkdir(parents=True, exist_ok=True)
PIPE_NDJSON = LOG_DIR / "pipeline.ndjson"
ERR_NDJSON  = LOG_DIR / "errors.ndjson"

def now_utc(): return datetime.datetime.now(datetime.timezone.utc)
def idem_key(obj): return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
def log_event(stage, mail_id, payload):
    rec={"ts":now_utc().isoformat(timespec="seconds"),"stage":stage,"mail_id":mail_id,"payload":payload}
    with PIPE_NDJSON.open("a", encoding="utf-8") as w: w.write(json.dumps(rec,ensure_ascii=False)+"\n")

SCHEMA={
"runs":"""CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, started_at TEXT, input_source TEXT, versions_json TEXT)""",
"actions":"""CREATE TABLE IF NOT EXISTS actions(run_id TEXT, mail_id TEXT, action TEXT, priority TEXT, queue TEXT, due_at TEXT, fields_json TEXT)""",
"outbox":"""CREATE TABLE IF NOT EXISTS outbox(mail_id TEXT, channel TEXT, subject TEXT, status TEXT, payload_json TEXT, sent_at TEXT)""",
"err_log":"""CREATE TABLE IF NOT EXISTS err_log(ts TEXT, mail_id TEXT, stage TEXT, message TEXT, traceback TEXT)"""
}
def db_conn(path:str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(path); con.execute("PRAGMA journal_mode=WAL"); 
    for sql in SCHEMA.values(): con.execute(sql)
    con.commit(); return con
def upsert_action(con, run_id, mid, action, pr, q, due_at, fields):
    con.execute("INSERT INTO actions(run_id,mail_id,action,priority,queue,due_at,fields_json) VALUES(?,?,?,?,?,?,?)",
                (run_id, mid, action, pr, q, due_at, json.dumps(fields,ensure_ascii=False))); con.commit()
def upsert_outbox(con, mid, channel, subject, status, payload):
    con.execute("INSERT INTO outbox(mail_id,channel,subject,status,payload_json,sent_at) VALUES(?,?,?,?,?,?)",
                (mid, channel, subject, status, json.dumps(payload,ensure_ascii=False), now_utc().isoformat(timespec="seconds"))); con.commit()

def parse_sla_hours(s):
    if not s: return None
    s=str(s).lower(); m=re.search(r"(\\d+)\\s*h", s) or re.search(r"(\\d+)\\s*hour", s)
    return int(m.group(1)) if m else None

def decide_priority_queue(action, fields):
    pr,q,due_hrs = "P3","Ops",72
    if action=="quarantine": pr,q,due_hrs=("P1","Security",1)
    elif action=="create_quote_ticket":
        pr,q,due_hrs=("P2","Sales",24)
        if fields.get("amount") and fields.get("date"): pr="P1"; due_hrs=8
    elif action=="create_support_ticket":
        pr,q,due_hrs=("P2","Support",8)
        env=(fields.get("env") or "").lower(); sla_h=parse_sla_hours(fields.get("sla"))
        if env=="prod" or (sla_h is not None and sla_h<=4): pr="P1"; due_hrs=min(4, sla_h or 4)
    elif action=="escalate_to_CX": pr,q,due_hrs=("P2","Support",24)
    elif action=="send_policy_docs": pr,q,due_hrs=("P3","Compliance",48)
    elif action=="update_profile": pr,q,due_hrs=("P3","CRM",48)
    due_at=(now_utc()+datetime.timedelta(hours=due_hrs)).isoformat(timespec="seconds")
    return pr,q,due_at

def act_support_ticket(out_dir:Path, mid:str, fields:dict):
    rec={"ticket_id": f"TS-{mid}","summary": f"Tech Support for {mid}",
         "severity": "P1" if ((fields.get("env","").lower()=="prod") or ((parse_sla_hours(fields.get("sla")) or 99) <= 4)) else "P2",
         "fields": fields,"created_at": now_utc().isoformat()}
    (out_dir/"tickets").mkdir(parents=True, exist_ok=True)
    fp=out_dir/"tickets"/f"ts_{mid}.json"; fp.write_text(json.dumps(rec,ensure_ascii=False,indent=2), encoding="utf-8"); return fp

def act_profile_diff(out_dir:Path, mid:str, body_text:str):
    name=re.search(r"(?:姓名|name)[:：]\\s*([^\\n]+)", body_text, re.I)
    phone=re.search(r"(?:電話|phone)[:：]\\s*([\\d\\-\\+\\s]{6,})", body_text, re.I)
    addr=re.search(r"(?:地址|address)[:：]\\s*([^\\n]+)", body_text, re.I)
    new={"name": name.group(1).strip() if name else None,
         "phone": phone.group(1).strip() if phone else None,
         "address": addr.group(1).strip() if addr else None}
    (out_dir/"diffs").mkdir(parents=True, exist_ok=True)
    dpf=out_dir/"diffs"/f"profile_diff_{mid}.json"
    dpf.write_text(json.dumps({"id":mid,"changes":{k:v for k,v in new.items() if v}},ensure_ascii=False,indent=2), encoding="utf-8")
    return dpf

def act_policy_rag(out_dir:Path, mid:str, text:str):
    q=(text or "").strip()[:200] or "退款 申請 條件"
    res=subprocess.run(["python","scripts/rag_faq.py","--query",q], capture_output=True, text=True)
    hits=[]; 
    try:
        j=json.loads(res.stdout); hits=j.get("hits",[])
    except Exception:
        hits=[]
    reply="您好，以下是與您的問題最相關的規則摘要：\\n\\n"
    for i,h in enumerate(hits[:3],1): reply += f"[{i}] 來源: {h.get('doc','')}\\n{(h.get('snippet') or '')[:600]}\\n\\n"
    (out_dir/"faq_replies").mkdir(parents=True, exist_ok=True)
    rf=out_dir/"faq_replies"/f"faq_reply_{mid}.txt"; rf.write_text(reply, encoding="utf-8")
    return rf, reply

def act_complaint_notify(out_dir:Path, mid:str):
    (out_dir/"notify").mkdir(parents=True, exist_ok=True)
    sh=out_dir/"notify"/f"notify_slack_{mid}.sh"
    sh.write_text("#!/usr/bin/env bash\\n# TODO: export SLACK_WEBHOOK\\n" +
                  "curl -s -X POST \"$SLACK_WEBHOOK\" -H 'Content-type: application/json' " +
                  "--data '{\"text\":\"[CX] 投訴升級: " + mid + "\"}'\\n", encoding="utf-8"); 
    os.chmod(sh,0o755); return sh

def act_quote(out_dir:Path, mid:str, fields:dict):
    val=fields.get("amount",{}); amt=val.get("value") if isinstance(val,dict) else val
    if isinstance(amt,str):
        m=re.search(r"(\\d[\\d,\\.]*)", amt); amt=float(m.group(1).replace(",","")) if m else None
    if not isinstance(amt,(int,float)): amt=10000.0
    tax=round(amt*0.05,2); total=round(amt+tax,2)
    date=(fields.get("date",{}) or {}).get("raw") or fields.get("date") or ""
    html="<html><body><h2>報價單</h2><p>案件：" + mid + "</p>" + \
         "<table border='1' cellpadding='6'><tr><th>金額</th><th>稅額(5%)</th><th>總計</th></tr>" + \
         "<tr><td>"+str(amt)+"</td><td>"+str(tax)+"</td><td>"+str(total)+"</td></tr></table>" + \
         "<p>有效期限：" + (date or "7 天內") + "</p></body></html>"
    (out_dir/"quotes").mkdir(parents=True, exist_ok=True)
    hf=out_dir/"quotes"/f"quote_{mid}.html"; hf.write_text(html, encoding="utf-8")
    try:
        from reportlab.lib.pagesizes import A4; from reportlab.pdfgen import canvas
        pf=out_dir/"quotes"/f"quote_{mid}.pdf"; c=canvas.Canvas(str(pf), pagesize=A4)
        c.drawString(72,800,"Quote for " + mid); c.drawString(72,780,f"Amount:{amt} Tax(5%):{tax} Total:{total}")
        c.drawString(72,760,"Valid until:" + (date or "7 days")); c.showPage(); c.save()
        pdf=str(pf)
    except Exception:
        pdf=""
    return hf, pdf

def read_jsonl(path:Path):
    if not Path(path).exists(): return []
    for ln in Path(path).read_text(encoding="utf-8",errors="ignore").splitlines():
        s=ln.strip()
        if not s: continue
        try: yield json.loads(s)
        except: pass

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--in_actions", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--mode", default="emit-sh", choices=["dryrun","emit-sh"])
    ap.add_argument("--model_versions", default="{}")  # 舊腳本相容
    # 新增參數（向下相容）
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run_id", default=None)
    ap.add_argument("--email-mode", default="file", choices=["file","smtp"])
    ap.add_argument("--send-emails", action="store_true")
    a=ap.parse_args()

    out=Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    con=db_conn(a.db)

    # run_id（若無，取父資料夾名或目前時間）
    run_id=a.run_id or Path(a.out_dir).parent.name or datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    con.execute("INSERT OR IGNORE INTO runs(run_id,started_at,input_source,versions_json) VALUES(?,?,?,?)",
        (run_id, datetime.datetime.utcnow().isoformat(timespec="seconds"), str(a.cases), a.model_versions or "{}")); con.commit()

    # Transport
    tx = SMTPTransport() if a.email_mode=="smtp" else FileTransport(out/"email_outbox")

    # 載入
    cases={ r.get("id",""): r for r in read_jsonl(a.cases) }
    actions=list(read_jsonl(a.in_actions))

    plan=out/"actions_plan.ndjson"
    with plan.open("w", encoding="utf-8") as w:
        for act in actions:
            mid = act.get("id","")
            akey= act.get("action","")
            fields = act.get("fields",{}) if isinstance(act.get("fields",{}),dict) else {}
            text  = (cases.get(mid,{}).get("body") or cases.get(mid,{}).get("text") or "")[:4000]

            pr,q,due_at = decide_priority_queue(akey, fields)
            payload={"id":mid,"action":akey,"priority":pr,"queue":q,"due_at":due_at,"fields":fields,
                     "audit":{"source":"sma_actions_exec","created_at":now_utc().isoformat(timespec='seconds')}}
            payload["idempotency_key"] = idem_key({"id":mid,"action":akey,"fields":fields})

            note=""
            try:
                if akey=="create_support_ticket":
                    fp=act_support_ticket(out, mid, fields); note="ticket="+fp.name
                    if a.send_emails: tx.send("support@example.com", "[Support] "+mid, "已建立技支工單", run_id, mid, akey)
                elif akey=="update_profile":
                    dpf=act_profile_diff(out, mid, text); note="diff="+dpf.name
                elif akey=="send_policy_docs":
                    rf,reply=act_policy_rag(out, mid, text); note="faq="+rf.name
                    if a.send_emails: tx.send(cases.get(mid,{}).get("from") or "user@example.com","[政策規則回覆]", reply, run_id, mid, akey)
                    upsert_outbox(con, mid, "email", "[政策規則回覆]", "sent" if a.send_emails else "prepared", {"file":str(rf)})
                elif akey=="escalate_to_CX":
                    sh=act_complaint_notify(out, mid); note="notify="+sh.name
                    if a.send_emails: tx.send("support@example.com", "[CX 升級] "+mid, "請儘速處理", run_id, mid, akey)
                elif akey=="create_quote_ticket":
                    hf,pdf=act_quote(out, mid, fields); note="quote="+Path(hf).name
                    if a.send_emails: tx.send(cases.get(mid,{}).get("from") or "client@example.com","[報價]", "附上報價，請查收。", run_id, mid, akey)
                    upsert_outbox(con, mid, "email", "[報價]", "sent" if a.send_emails else "prepared", {"html":str(hf),"pdf":pdf})
                elif akey=="quarantine":
                    pass  # 只做審計
                # DB 寫入
                upsert_action(con, run_id, mid, akey, pr, q, due_at, fields)
                payload["_note"]=note
                w.write(json.dumps(payload,ensure_ascii=False)+"\n")
                log_event("action", mid, {"action":akey,"priority":pr,"queue":q})
            except Exception as e:
                with ERR_NDJSON.open("a",encoding="utf-8") as we:
                    we.write(json.dumps({"when":now_utc().isoformat(timespec="seconds"),"mail_id":mid,"stage":"action","message":str(e)},ensure_ascii=False)+"\n")

            if a.mode=="emit-sh":
                sh=out/("do_"+mid+"_"+akey+".sh")
                sh.write_text("#!/usr/bin/env bash\nset -euo pipefail\ncat payload_"+mid+"_"+akey+".json\n", encoding="utf-8")
                os.chmod(sh,0o755)
            (out/("payload_"+mid+"_"+akey+".json")).write_text(json.dumps(payload,ensure_ascii=False,indent=2), encoding="utf-8")

    print("[OK] RPA out ->", out, "items=", len(actions))

if __name__=="__main__": main()
