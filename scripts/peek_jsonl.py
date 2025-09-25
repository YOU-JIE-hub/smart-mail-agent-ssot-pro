#!/usr/bin/env python
import sys, json, itertools
path = sys.argv[1] if len(sys.argv)>1 else None
if not path: 
    print("[FATAL] 用法: scripts/peek_jsonl.py <file.jsonl>", file=sys.stderr); sys.exit(2)
rows = []
with open(path, "r", encoding="utf-8") as f:
    for i, line in zip(range(5), f):
        line=line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except Exception as e: print(f"[WARN] line parse error: {e}", file=sys.stderr)
keys = sorted(set().union(*[r.keys() for r in rows])) if rows else []
print(json.dumps({"file": path, "n_peek": len(rows), "keys": keys, "samples": rows}, ensure_ascii=False, indent=2))
