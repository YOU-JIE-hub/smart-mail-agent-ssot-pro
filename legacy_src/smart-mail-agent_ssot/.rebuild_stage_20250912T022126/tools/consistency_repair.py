from __future__ import annotations
from pathlib import Path
import re, json, sqlite3, argparse, time

RUN_RE=re.compile(r"^\d{8}T\d{6}$")
def runs(root:Path): 
    return [p.name for p in sorted(root.glob("*")) if p.is_dir() and RUN_RE.match(p.name)]

def load_events(path:Path)->list[dict]:
    if not path.exists(): return []
    out=[]
    for ln in path.read_text("utf-8").splitlines():
        try: out.append(json.loads(ln))
        except Exception: pass
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=12)
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--root", default="reports_auto/e2e_mail")
    ap.add_argument("--evdir", default="reports_auto/events")
    args=ap.parse_args()
    root=Path(args.root); evdir=Path(args.evdir); db=Path(args.db)
    rs=runs(root)[-args.window:]
    added_ev=0; added_db=0
    con=None
    if db.exists():
        con=sqlite3.connect(str(db)); cur=con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS actions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_ts TEXT, case_id TEXT, action TEXT, status TEXT,
          payload_ref TEXT, idempotency_key TEXT, created_at TEXT, meta_json TEXT
        )""")
        con.commit()
    for r in rs:
        sent=root/r/"rpa_out"/"email_sent"
        if not sent.exists(): continue
        evp=evdir/f"{r}.ndjson"
        events=load_events(evp)
        already_ev={e.get("idem") for e in events if e.get("action")=="send_email"}
        if con:
            cur=con.cursor()
            cur.execute("SELECT idempotency_key FROM actions WHERE action='SendEmail' AND run_ts=?", (r,))
            already_db={row[0].split(":")[1] for row in cur.fetchall() if ":" in (row[0] or "")}
        else:
            already_db=set()
        # 以 .eml 為權威
        for eml in sorted(sent.glob("*.eml")):
            stem=eml.stem
            # 事件補齊
            if stem not in already_ev:
                evdir.mkdir(parents=True, exist_ok=True)
                with (evp).open("a", encoding="utf-8") as w:
                    w.write(json.dumps({
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "run_ts": r, "kind":"runner","level":"INFO",
                        "idem": stem, "case_id": None, "intent": None,
                        "action":"send_email","result":"backfill_fs"
                    }, ensure_ascii=False)+"\n")
                added_ev+=1
            # DB 補齊
            if con and stem not in already_db:
                idem=f"{r}:{stem}:SendEmail"
                cur.execute("""INSERT OR IGNORE INTO actions
                  (run_ts,case_id,action,status,payload_ref,idempotency_key,created_at,meta_json)
                  VALUES (?,?,?,?,?,?,datetime('now'),json_object('source','repair'))""",
                  (r, stem, "SendEmail", "succeeded", str(eml), idem))
                added_db+=int(cur.rowcount>0)
        if con: con.commit()
    if con: con.close()
    print(f"[OK] repair: added_events={added_ev} added_db={added_db}")
if __name__=="__main__": main()
