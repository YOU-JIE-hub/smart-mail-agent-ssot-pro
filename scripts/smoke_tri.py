import os, json, time
from pathlib import Path
import requests as r
STATUS=Path("reports_auto/status"); STATUS.mkdir(parents=True, exist_ok=True)
def jdump(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),"utf-8")
base=os.environ.get("SMA_API_BASE","http://127.0.0.1:8088")
meta=r.get(f"{base}/debug/model_meta",timeout=10).json(); jdump(STATUS/"SMOKE_META.json",meta)
cls=r.post(f"{base}/classify",json={"text":"Hello I need a quote.","route":"rule"},timeout=10).json(); jdump(STATUS/"SMOKE_CLASSIFY.json",cls)
extr=r.post(f"{base}/extract",json={"text":"請撥打 02-1234-5678，金額 3000 元"},timeout=10).json(); jdump(STATUS/"SMOKE_EXTRACT.json",extr)
print("[smoke] ok",time.time())
