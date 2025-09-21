from __future__ import annotations
from pathlib import Path
import json
def main():
    base=Path("reports_auto/events"); out=Path("reports_auto/metrics/daily.json")
    kpi={}
    for f in sorted(base.glob("*.ndjson")):
        day=f.stem[:8]; 
        if day not in kpi: kpi[day]={"runs":0,"e2e_done":0,"e2e_fail":0,"hil_blocked":0}
        kpi[day]["runs"]+=1
        for line in f.read_text("utf-8", errors="ignore").splitlines():
            try: ev=json.loads(line)
            except: continue
            act=ev.get("action")
            if act=="e2e_done": kpi[day]["e2e_done"]+=1
            elif act=="e2e_fail": kpi[day]["e2e_fail"]+=1
            elif act=="hil_blocked": kpi[day]["hil_blocked"]+=1
    out.write_text(json.dumps(kpi, indent=2, ensure_ascii=False), "utf-8")
    print(f"[OK] rollup -> {out}")
if __name__=="__main__": main()
