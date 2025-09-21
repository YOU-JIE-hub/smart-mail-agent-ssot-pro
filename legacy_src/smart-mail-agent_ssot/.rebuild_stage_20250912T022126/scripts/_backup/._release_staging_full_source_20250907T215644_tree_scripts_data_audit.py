#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, re, time
from pathlib import Path
ROOT=Path(".").resolve()
TS=time.strftime("%Y%m%dT%H%M%S")
OUT=ROOT/f"reports_auto/data_audit/{TS}"
OUT.mkdir(parents=True, exist_ok=True)

def audit_jsonl(p, kind):
    rows=[json.loads(x) for x in open(p,"r",encoding="utf-8") if x.strip()]
    TPL=re.compile(r"(unsubscribe|http[s]?://|抽獎|lottery|USDT|色情)", re.I)
    texts=[(r.get("text") or "").strip() for r in rows]
    hits=sum(1 for t in texts if TPL.search(t))
    md=OUT/f"{kind}.md"
    with open(md,"w",encoding="utf-8") as f:
        f.write(f"# Data audit - {kind}\n- file: {p}\n- size: {len(rows)}\n- template_like_ratio: {hits/len(rows):.3f}\n")
    print("[OK] write", md)

for p in [ROOT/"data/spam_eval/dataset.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if p.exists():
        audit_jsonl(p, p.parts[-2])
