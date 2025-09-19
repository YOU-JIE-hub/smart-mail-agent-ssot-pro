#!/usr/bin/env python3
import argparse, json, sqlite3
from pathlib import Path

def cols(conn): return {r[1] for r in conn.execute("PRAGMA table_info(actions);")}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="db/sma.sqlite")
    ap.add_argument("--run-dir",required=True)
    a=ap.parse_args()
    run=Path(a.run_dir); run_ts=run.name
    plan=run/"actions_plan.ndjson"
    if not plan.exists(): raise SystemExit(f"[FATAL] not found: {plan}")
    conn=sqlite3.connect(a.db); cur=conn.cursor()
    c=cols(conn)
    tcol="type" if "type" in c else ("action_type" if "action_type" in c else ("action" if "action" in c else None))
    pcol="payload_json" if "payload_json" in c else ("payload_ref" if "payload_ref" in c else None)
    has_run="run_ts" in c; has_s="started_at" in c; has_e="ended_at" in c
    if not tcol or not pcol: raise SystemExit("[FATAL] actions 表缺必要欄位")
    ins=ign=0
    for line in plan.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        rec=json.loads(line); cid=rec["case_id"]
        for step in rec["steps"]:
            idem=step["idempotency_key"]; t=step["type"]; hil=step.get("hil_gate",False)
            st="skipped_by_hil" if (t=="SendEmail" and hil) else "planned"
            if cur.execute("SELECT 1 FROM actions WHERE idempotency_key=?;",(idem,)).fetchone(): ign+=1; continue
            cols_ins=["case_id",tcol,"status","idempotency_key",pcol]; vals=[cid,t,st,idem,None]
            if has_run: cols_ins.append("run_ts"); vals.append(run_ts)
            if has_s: cols_ins.append("started_at"); vals.append(None)
            if has_e: cols_ins.append("ended_at"); vals.append(None)
            cur.execute(f"INSERT INTO actions({','.join(cols_ins)}) VALUES({','.join(['?']*len(vals))});", vals); ins+=1
    conn.commit(); print(f"[OK] actions synced: inserted={ins}, ignored_existing={ign}, run_ts={run_ts}")
if __name__=="__main__": main()
