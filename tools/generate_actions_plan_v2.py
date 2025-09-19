#!/usr/bin/env python3
import argparse, json, sqlite3, sys
from pathlib import Path
from collections import defaultdict

INTENT_MAP = {
    "規則詢問": ["FAQReply"],
    "報價": ["GenerateQuote", "SendEmail"],
    "技術支援": ["CreateTicket", "SendEmail"],
    "投訴": ["CreateTicket", "SendEmail"],
    "資料異動": ["GenerateDiff", "SendEmail"],
}

def latest_intent(conn, case_id: str):
    # 取該 case 最新一筆意圖與信心（兼容無 confidence 欄）
    row = conn.execute("""
        SELECT intent,
               COALESCE(confidence, 0.85) AS conf
        FROM intent_preds
        WHERE case_id = ?
        ORDER BY COALESCE(created_at, ts) DESC
        LIMIT 1
    """, (case_id,)).fetchone()
    return (row[0], float(row[1])) if row else (None, 0.0)

def load_cases(run_dir: Path):
    items=[]
    with open(run_dir/"cases.jsonl","r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if ln: items.append(json.loads(ln))
    return items

def build_steps(intent: str|None, conf: float, case_id: str, run_ts: str, hil_thr: float):
    steps=[]
    if not intent:
        steps.append({
            "type": "SendEmail",
            "preconditions": ["has_reply_body"],
            "retries": 2,
            "compensations": [],
            "hil_gate": True,
            "idempotency_key": f"{run_ts}:{case_id}:SendEmail"
        })
        return "N/A", 0.0, steps
    seq = INTENT_MAP.get(intent, ["SendEmail"])
    for typ in seq:
        steps.append({
            "type": typ,
            "preconditions": (["parsed_ok"] if typ in ("GenerateQuote","GenerateDiff") else []),
            "retries": 2,
            "compensations": [],
            "hil_gate": (conf < hil_thr),
            "idempotency_key": f"{run_ts}:{case_id}:{typ}"
        })
    return intent, conf, steps

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--hil-thr", type=float, default=0.80)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_ts = run_dir.name
    if not (run_dir/"cases.jsonl").exists():
        print(f"[FATAL] not found: {run_dir}/cases.jsonl", file=sys.stderr); sys.exit(3)

    conn = sqlite3.connect(args.db)
    out = []
    for c in load_cases(run_dir):
        case_id = c.get("id") or c.get("case_id")
        if not case_id: continue
        intent, conf = latest_intent(conn, case_id)
        intent, conf, steps = build_steps(intent, conf, case_id, run_ts, args.hil_thr)
        out.append({
            "case_id": case_id,
            "intent": intent,
            "confidence": round(conf, 4),
            "steps": steps,
        })
    conn.close()

    # 覆寫本批 actions_plan.ndjson
    with open(run_dir/"actions_plan.ndjson","w",encoding="utf-8") as w:
        for obj in out:
            w.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(f"[OK] actions_plan written → {run_dir/'actions_plan.ndjson'} (cases={len(out)})")

if __name__ == "__main__":
    main()
