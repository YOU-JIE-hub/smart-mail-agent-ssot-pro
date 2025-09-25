#!/usr/bin/env python3
import argparse, json, sqlite3, time
from pathlib import Path

INTENT_MAP = {
    "規則詢問": ["FAQReply"],
    "報價": ["GenerateQuote", "SendEmail"],
    "技術支援": ["CreateTicket", "SendEmail"],
    "投訴": ["CreateTicket", "SendEmail"],
    "資料異動": ["GenerateDiff", "SendEmail"],
}

def load_cases(run_dir: Path):
    cases = []
    with open(run_dir/"cases.jsonl","r",encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if line: cases.append(json.loads(line))
    return cases

def latest_intent_for(conn, case_id: str):
    row = conn.execute("""
      SELECT label, COALESCE(confidence, 0.0) AS conf
      FROM intent_preds
      WHERE case_id=?
      ORDER BY created_at DESC
      LIMIT 1
    """, (case_id,)).fetchone()
    if row is None: return ("一般回覆", 0.0)
    return (row[0], float(row[1]))

def make_steps(intent: str, conf: float, hil_thr: float = 0.70):
    acts = INTENT_MAP.get(intent, ["SendEmail"])
    steps = []
    for a in acts:
        step = {
            "type": a,
            "preconditions": [],
            "retries": 2,
            "compensations": [],
            "hil_gate": conf < hil_thr  # 低信心就加人審門檻
        }
        # 最小前置條件（可按需擴充）
        if a in ("GenerateQuote","GenerateDiff"):
            step["preconditions"] = ["parsed_ok"]
        if a == "SendEmail":
            step["preconditions"] = ["has_reply_body"]
        steps.append(step)
    return steps

def append_summary(run_dir: Path, counts: dict, hil_cases: int):
    sm = run_dir/"SUMMARY.md"
    lines = []
    lines.append("\n## Action Plan")
    lines.append(f"- Cases planned: {sum(counts.values())}")
    lines.append(f"- With HIL gate (low confidence): {hil_cases}")
    lines.append("- Steps by type:")
    for k,v in sorted(counts.items()):
        lines.append(f"  - {k}: {v}")
    with open(sm,"a",encoding="utf-8") as f:
        f.write("\n".join(lines)+"\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    out_path = run_dir/"actions_plan.ndjson"
    cases = load_cases(run_dir)

    conn = sqlite3.connect(args.db)
    run_ts = time.strftime("%Y%m%dT%H%M%S")
    step_type_counts = {}
    hil_cases = 0

    with open(out_path,"w",encoding="utf-8") as w:
        for c in cases:
            cid = c["id"]
            intent, conf = latest_intent_for(conn, cid)
            steps = make_steps(intent, conf)
            # 統計
            if any(s.get("hil_gate") for s in steps): hil_cases += 1
            for s in steps:
                step_type_counts[s["type"]] = step_type_counts.get(s["type"],0)+1
                s["idempotency_key"] = f"{run_ts}:{cid}:{s['type']}"
            plan = {
                "case_id": cid,
                "intent": intent,
                "confidence": conf,
                "steps": steps
            }
            w.write(json.dumps(plan, ensure_ascii=False)+"\n")

    conn.close()
    append_summary(run_dir, step_type_counts, hil_cases)
    print(f"[OK] actions_plan written → {out_path}")
    print(f"[OK] SUMMARY.md appended (Action Plan)")

if __name__ == "__main__":
    main()
