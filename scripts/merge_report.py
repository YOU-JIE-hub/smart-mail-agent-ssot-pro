import os,sys,json,time
from pathlib import Path
SRC=Path(sys.argv[1]); OUT=Path(sys.argv[2])
pieces=[]
def add(title,txt): pieces.append(f"## {title}\\n\\n"+txt+"\\n")
def slurp(p): return Path(p).read_text("utf-8",errors="ignore") if Path(p).exists() else "(missing)"
add("Model Meta (API smoke)", slurp("reports_auto/status/SMOKE_META.json"))
add("Run Metrics", slurp(SRC/"metrics.json"))
OUT.write_text("# MODEL REPORT\\n\\n"+ "\\n".join(pieces), "utf-8")
print("[report] done ->", OUT)
