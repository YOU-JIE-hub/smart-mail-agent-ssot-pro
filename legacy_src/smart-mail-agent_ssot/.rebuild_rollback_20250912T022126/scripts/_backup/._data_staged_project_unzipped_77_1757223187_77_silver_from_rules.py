#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, re, sys, yaml
from pathlib import Path

def load_rules(p: Path):
    obj = yaml.safe_load(p.read_text(encoding="utf-8"))
    pats = {k:[re.compile(rx, re.I) for rx in v] for k,v in obj.get("patterns",{}).items()}
    return pats

def spans(text, pats):
    out=[]
    for lab, rxs in pats.items():
        for r in rxs:
            for m in r.finditer(text):
                out.append((m.start(), m.end(), lab))
    out = sorted(set(out))
    return [{"start":s, "end":e, "label":l} for s,e,l in out]

def run(in_path, out_path, rules_path):
    pats = load_rules(Path(rules_path))
    n=0
    with open(in_path, encoding="utf-8") as fi, open(out_path, "w", encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text","")
            fo.write(json.dumps({"text":t,"spans":spans(t,pats)}, ensure_ascii=False)+"\n")
            n+=1
    print(f"[SILVER] {in_path} -> {out_path} lines={n}")

if __name__ == "__main__":
    IN, OUT, RULES = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv)>3 else ".sma_tools/ruleset.yml")
    run(IN, OUT, RULES)
