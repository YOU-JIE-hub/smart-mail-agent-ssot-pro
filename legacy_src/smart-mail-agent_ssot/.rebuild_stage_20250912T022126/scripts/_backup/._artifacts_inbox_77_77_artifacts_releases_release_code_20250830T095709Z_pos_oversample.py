#!/usr/bin/env python3
import json, random, argparse
from pathlib import Path
R=random.Random(42)
ap=argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", dest="out", required=True)
ap.add_argument("--target_pos_ratio", type=float, default=0.7)
args=ap.parse_args()
rows=[json.loads(x) for x in Path(args.inp).open(encoding="utf-8")]
pos=[r for r in rows if r.get("spans")]
neg=[r for r in rows if not r.get("spans")]
def ratio(p,n): p=len(p); n=len(n); return p/(p+n) if p+n else 0.0
out=list(rows)
while ratio(pos,neg) < args.target_pos_ratio and pos:
    out.append(R.choice(pos))
R.shuffle(out)
Path(args.out).write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in out)+"\n",encoding="utf-8")
print(f"[OVERSAMPLE] in={len(rows)} -> out={len(out)} target_pos_ratio={args.target_pos_ratio}")
