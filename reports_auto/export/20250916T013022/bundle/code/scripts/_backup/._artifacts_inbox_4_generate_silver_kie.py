#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, re
from pathlib import Path
import yaml
def load_rules(p: Path):
    obj = yaml.safe_load(p.read_text(encoding="utf-8"))
    labels = obj.get("labels", []) or []
    pats = {k: [re.compile(rx, re.I) for rx in (v or [])] for k, v in (obj.get("patterns", {}) or {}).items()}
    return labels, pats
def find_spans(text: str, label: str, regexes):
    spans=[]; 
    for rgx in regexes:
        for m in rgx.finditer(text):
            spans.append({"start":m.start(),"end":m.end(),"label":label})
    return spans
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True)
    ap.add_argument("--out_jsonl", required=True)
    ap.add_argument("--rules", default=".sma_tools/ruleset.yml")
    args=ap.parse_args()
    in_p, out_p, rules_p = Path(args.in_jsonl), Path(args.out_jsonl), Path(args.rules)
    if not in_p.exists(): raise SystemExit(f"[FATAL] input not found: {in_p}")
    labels, pats = load_rules(rules_p)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    n=0
    with in_p.open("r",encoding="utf-8") as fi, out_p.open("w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text") or o.get("body") or ""
            spans=[]
            for lab in labels:
                if lab in pats: spans += find_spans(t, lab, pats[lab])
            fo.write(json.dumps({"text":t,"spans":spans}, ensure_ascii=False)+"\n"); n+=1
    print(f"[SILVER] wrote={n} -> {out_p}")
if __name__ == "__main__": main()
