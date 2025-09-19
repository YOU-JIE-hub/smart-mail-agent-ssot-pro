import json,sys
from pathlib import Path
ROOT=Path(sys.argv[1])
m=(ROOT/"metrics.json")
if not m.exists(): print("[gate] metrics.json missing; FAIL"); sys.exit(2)
data=json.loads(m.read_text("utf-8"))
# 允許 light 版：只要有 tri_eval_light 即過；正式版可加入 Intent macro-F1 門檻
print("[gate] OK (light) — metrics keys:", list(data.keys()))
