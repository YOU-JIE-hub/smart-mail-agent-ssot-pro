import os, json
from pathlib import Path
ROOT=Path.cwd(); ts=os.popen("date +%Y%m%dT%H%M%S").read().strip()
ctx=ROOT/f"reports_auto/context_{ts}"; ctx.mkdir(parents=True,exist_ok=True)
(ctx/"CONTEXT_SUMMARY.txt").write_text("\\n".join([f"root={ROOT}", f"ts={ts}"]), "utf-8")
# 目錄樹（精簡）
def tree():
 out=[]
 for dp, dn, fn in os.walk(ROOT):
  dp=Path(dp); rel=dp.relative_to(ROOT).as_posix() or "."
  if any(rel.startswith(x) for x in [".git",".venv","venv","node_modules","models","weights","datasets","data","reports_auto/logs"]): continue
  out.append(rel+"/");
  for n in sorted(fn): out.append((dp.relative_to(ROOT).as_posix() or ".")+"/"+n)
 return "\\n".join(out)
(ctx/"TREE.txt").write_text(tree(),"utf-8")
os.system(f"(cd reports_auto && zip -q -r context_capsule_{ts}.zip context_{ts})")
print("[context] zip ->", f"reports_auto/context_capsule_{ts}.zip")
