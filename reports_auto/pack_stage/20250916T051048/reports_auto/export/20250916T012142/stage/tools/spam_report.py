from __future__ import annotations
from pathlib import Path
import json, re
src=Path("reports_auto/prod_quick_report.md")
out=Path("metrics/spam_metrics.json"); out.parent.mkdir(parents=True, exist_ok=True)
m={"TEXT":None,"RULE":None,"ENSEMBLE":None}
if src.exists():
    t=src.read_text(encoding="utf-8")
    m["TEXT"]=float(re.search(r"TEXT Macro-F1:\s*([0-9.]+)",t).group(1))
    m["RULE"]=float(re.search(r"RULE Macro-F1:\s*([0-9.]+)",t).group(1))
    m["ENSEMBLE"]=float(re.search(r"ENSEMBLE Macro-F1:\s*([0-9.]+)",t).group(1))
out.write_text(json.dumps(m,ensure_ascii=False,indent=2), encoding="utf-8")
print("[SPAM] metrics ->", out)
