
from __future__ import annotations
import json, pathlib, sys

src = pathlib.Path("fixtures/eval_set.jsonl")
dst = pathlib.Path("reports_auto/kie/_from_fixtures.jsonl")
dst.parent.mkdir(parents=True, exist_ok=True)

if not src.exists():
    print("[KIE] fixtures/eval_set.jsonl not found", file=sys.stderr)
    sys.exit(0)

with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
    for ln in fin:
        try:
            o=json.loads(ln); e=o.get("email",{})
            t=(e.get("subject","")+"\n"+e.get("body","")).strip()
            fout.write(json.dumps({"text": t}, ensure_ascii=False)+"\n")
        except Exception:
            continue
print(str(dst))
