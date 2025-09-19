#!/usr/bin/env python3
import argparse, json, re, yaml
from pathlib import Path
def load_rules(p):
    obj = yaml.safe_load(Path(p).read_text(encoding="utf-8"))
    pats = {k:[re.compile(rx, re.I) for rx in v] for k,v in obj.get("patterns",{}).items()}
    return pats
def spans(text, pats):
    out=[]
    for lab, rxs in pats.items():
        for rgx in rxs:
            for m in rgx.finditer(text):
                out.append({"start":m.start(),"end":m.end(),"label":lab})
    return sorted(out, key=lambda s:(s["start"],s["end"]))
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True)
    ap.add_argument("--out_jsonl", required=True)
    ap.add_argument("--rules", default=".sma_tools/ruleset.yml")
    args=ap.parse_args()
    pats=load_rules(args.rules)
    ip,op=Path(args.in_jsonl),Path(args.out_jsonl); op.parent.mkdir(parents=True, exist_ok=True)
    n=0
    with ip.open("r",encoding="utf-8") as fi, op.open("w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text") or o.get("body") or ""
            fo.write(json.dumps({"text":t,"spans":spans(t,pats)},ensure_ascii=False)+"\n"); n+=1
    print(f"[SILVER] wrote={n} -> {op}")
if __name__=="__main__": main()
