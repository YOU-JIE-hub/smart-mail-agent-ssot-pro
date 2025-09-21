#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 intent_reroute_audit.csv 或 intent_reroute_suggestion.ndjson 的最終意圖
覆蓋回指定 run 的 cases.jsonl（就地覆寫並備份）
"""
import argparse, csv, json, time
from pathlib import Path

def load_final_map(run: Path):
    csvp = run/"intent_reroute_audit.csv"
    ndp  = run/"intent_reroute_suggestion.ndjson"
    m={}
    if csvp.exists():
        with open(csvp, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cid=row.get("id") or row.get("case_id")
                fin=row.get("final_intent") or row.get("final")
                if cid and fin: m[cid]=fin
    elif ndp.exists():
        for ln in open(ndp,"r",encoding="utf-8"):
            try:
                j=json.loads(ln); cid=j.get("id") or j.get("case_id"); fin=j.get("final") or j.get("final_intent")
                if cid and fin: m[cid]=fin
            except Exception:
                pass
    return m

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args=ap.parse_args()
    run=Path(args.run_dir)
    cj=run/"cases.jsonl"
    assert cj.exists(), f"missing cases.jsonl: {cj}"
    ts=time.strftime("%Y%m%dT%H%M%S")
    bak=cj.with_name(cj.name+f".bak_{ts}")
    bak.write_text(cj.read_text(encoding="utf-8"), encoding="utf-8")

    m=load_final_map(run)
    rows=[json.loads(x) for x in cj.read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in rows:
        fin=m.get(r.get("id"))
        if fin: r["intent"]=fin

    with open(cj, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False)+"\n")
    print("[OK] cases.jsonl overwritten with final intents ->", cj)

if __name__=="__main__":
    main()
