#!/usr/bin/env python3
import argparse, json, sqlite3, os, shutil
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path(os.getenv("SMA_LOG_DIR","reports_auto/logs")); LOG_DIR.mkdir(parents=True, exist_ok=True)
PIPE_NDJSON = LOG_DIR/"pipeline.ndjson"

SCHEMA={
"runs":"""CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, started_at TEXT, input_source TEXT, versions_json TEXT)""",
"mails":"""CREATE TABLE IF NOT EXISTS mails(mail_id TEXT, run_id TEXT, from_addr TEXT, subject TEXT, received_at TEXT, meta_json TEXT)""",
"intent_preds":"""CREATE TABLE IF NOT EXISTS intent_preds(mail_id TEXT, top TEXT, p1 REAL, top2 TEXT, gap REAL, final TEXT)""",
"kie_spans":"""CREATE TABLE IF NOT EXISTS kie_spans(mail_id TEXT, label TEXT, start INTEGER, end INTEGER, raw_text TEXT)""",
"actions":"""CREATE TABLE IF NOT EXISTS actions(run_id TEXT, mail_id TEXT, action TEXT, priority TEXT, queue TEXT, due_at TEXT, fields_json TEXT)"""
}
def con_db(path:str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(path); con.execute("PRAGMA journal_mode=WAL")
    for s in SCHEMA.values(): con.execute(s); con.commit()
    return con
def read_jsonl(p:Path):
    if not p.exists(): return []
    for ln in p.read_text(encoding="utf-8",errors="ignore").splitlines():
        s=ln.strip()
        if s:
            try: yield json.loads(s)
            except: pass

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--run_dir", required=True); ap.add_argument("--db", default="db/sma.sqlite"); a=ap.parse_args()
    run=Path(a.run_dir); con=con_db(a.db); run_id=run.name
    con.execute("INSERT OR IGNORE INTO runs(run_id,started_at,input_source,versions_json) VALUES(?,?,?,?)",
        (run_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), str(run/'cases.jsonl'), "{}")); con.commit()
    # mails
    for r in read_jsonl(run/"cases.jsonl"):
        con.execute("INSERT INTO mails(mail_id,run_id,from_addr,subject,received_at,meta_json) VALUES(?,?,?,?,?,?)",
            (r.get("id",""), run_id, r.get("from") or "", r.get("subject") or "", "", json.dumps({"has_body":bool(r.get("body"))},ensure_ascii=False)))
    con.commit()
    # intent
    ip=run/"intent_preds.jsonl"
    if not ip.exists():
        tmp=Path("reports_auto/_tmp_e2e/intent_preds.jsonl")
        if tmp.exists(): shutil.copy2(tmp, ip)
    for r in read_jsonl(ip):
        top = r.get("final") or r.get("pred") or r.get("label") or r.get("top") or ""
        p1  = r.get("p1") or r.get("score") or 0.0
        top2= r.get("top2") or ""
        gap = r.get("gap") or 0.0
        con.execute("INSERT INTO intent_preds(mail_id,top,p1,top2,gap,final) VALUES(?,?,?,?,?,?)",
            (r.get("id",""), r.get("top") or top, float(p1), top2, float(gap), top))
    con.commit()
    # kie spans
    for r in read_jsonl(run/"kie_pred.jsonl"):
        for s in r.get("spans",[]):
            con.execute("INSERT INTO kie_spans(mail_id,label,start,end,raw_text) VALUES(?,?,?,?,?)",
                (r.get("id",""), s.get("label",""), int(s.get("start",0)), int(s.get("end",0)), ""))
    con.commit()
    # actions
    for r in read_jsonl(run/"actions.jsonl"):
        con.execute("INSERT INTO actions(run_id,mail_id,action,priority,queue,due_at,fields_json) VALUES(?,?,?,?,?,?,?)",
            (run_id, r.get("id",""), r.get("action",""), r.get("priority","P3"), r.get("queue","Ops"), r.get("due_at") or "", json.dumps(r.get("fields",{}),ensure_ascii=False)))
    con.commit()
    with PIPE_NDJSON.open("a",encoding="utf-8") as w:
        w.write(json.dumps({"ts":datetime.now(timezone.utc).isoformat(timespec="seconds"),"stage":"post_audit","run_dir":str(run)},ensure_ascii=False)+"\n")
    print("[OK] Post-audit -> DB + logs:", a.db, LOG_DIR)
