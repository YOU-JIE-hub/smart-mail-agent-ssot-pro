#!/usr/bin/env python3
import argparse, json, sqlite3
from pathlib import Path

INTENT_MAP={
 "規則詢問":["FAQReply"],
 "報價":["GenerateQuote","SendEmail"],
 "技術支援":["CreateTicket","SendEmail"],
 "投訴":["CreateTicket","SendEmail"],
 "資料異動":["GenerateDiff","SendEmail"],
}

def detect_cols(conn):
    t=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='intent_preds'").fetchone()
    if not t: return (None,None,False)
    cols={r[1] for r in conn.execute("PRAGMA table_info(intent_preds)")}
    ic=next((c for c in ["intent","label","pred","final","intent_label"] if c in cols), None)
    cc=next((c for c in ["confidence","conf","prob","probability","score"] if c in cols), None)
    return (ic,cc,True)

def latest_from_db(conn,cid,ic,cc):
    if not ic: return None
    conf=f"COALESCE({cc},0.85)" if cc else "0.85"
    r=conn.execute(f"SELECT {ic},{conf} FROM intent_preds WHERE case_id=? ORDER BY COALESCE(created_at,ts) DESC LIMIT 1;",(cid,)).fetchone()
    return (r[0], float(r[1])) if r else None

def latest_from_ndjson(run,cid):
    p=Path("reports_auto/logs/pipeline.ndjson")
    if not p.exists(): return None
    intent,conf=None,None
    for line in p.read_text(encoding="utf-8").splitlines():
        if '"kind": "e2e_case"' not in line: continue
        if f'"case_id": "{cid}"' not in line: continue
        try:
            o=json.loads(line); intent=o.get("intent"); conf=o.get("intent_conf",0.85)
        except: pass
    return (intent,float(conf) if conf is not None else 0.85) if intent else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="db/sma.sqlite")
    ap.add_argument("--run-dir",required=True)
    ap.add_argument("--hil-thr",type=float,default=0.80)
    a=ap.parse_args()
    run=Path(a.run-dir if hasattr(a,'run-dir') else a.run_dir)  # safety
    run=Path(a.run_dir); run_ts=run.name
    conn=sqlite3.connect(a.db)
    ic,cc,ok=detect_cols(conn)
    items=[]
    for line in (run/"cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        c=json.loads(line); cid=c.get("id") or c.get("case_id"); 
        if not cid: continue
        got=latest_from_db(conn,cid,ic,cc) if ok else None
        if not got: got=latest_from_ndjson(run,cid)
        intent,conf=(got or (None,0.0))
        steps=[]
        if intent in INTENT_MAP:
            for t in INTENT_MAP[intent]:
                steps.append({
                    "type":t, "preconditions": ["parsed_ok"] if t in ("GenerateQuote","GenerateDiff") else [],
                    "retries":2,"compensations":[],
                    "hil_gate": (conf<a.hil_thr and t=="SendEmail"),
                    "idempotency_key": f"{run_ts}:{cid}:{t}"
                })
        else:
            steps.append({"type":"SendEmail","preconditions":["has_reply_body"],"retries":2,"compensations":[],"hil_gate":True,"idempotency_key": f"{run_ts}:{cid}:SendEmail"})
        items.append({"case_id":cid,"intent":intent or "N/A","confidence":round(conf,4),"steps":steps})
    with open(run/"actions_plan.ndjson","w",encoding="utf-8") as w:
        for it in items: w.write(json.dumps(it,ensure_ascii=False)+"\n")
    print(f"[OK] actions_plan written → {run/'actions_plan.ndjson'} (cases={len(items)})")
if __name__=="__main__": main()
