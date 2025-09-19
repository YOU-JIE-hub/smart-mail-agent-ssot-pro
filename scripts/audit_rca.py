import os,glob,time
from pathlib import Path
STATUS=Path("reports_auto/status"); LOGS=Path("reports_auto/logs")
STATUS.mkdir(parents=True,exist_ok=True)
ts=time.strftime("%Y%m%dT%H%M%S")
out=STATUS/f"RCA_{ts}.md"
lines=["# RCA", "", f"- ts: {ts}", ""]
for p in sorted(glob.glob(str(LOGS/"*.err")))[-20:]: 
 try: tail="\\n".join(Path(p).read_text("utf-8",errors="ignore").splitlines()[-200:])
 except Exception: tail="(unreadable)"
 lines.append(f"## {os.path.basename(p)}\\n\\n```\\n{tail}\\n```\\n")
out.write_text("\\n".join(lines),"utf-8")
print("[audit] ->", out)
