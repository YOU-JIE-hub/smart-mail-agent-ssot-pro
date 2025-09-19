from __future__ import annotations
import os, time, pathlib, json
def notify(channel:str, text:str, out_dir="reports_auto/actions/slack"):
    dry = os.environ.get("SMA_DRY_RUN","1")!="0"
    od=pathlib.Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    fn=od/f"{time.strftime('%Y%m%dT%H%M%S')}.json"
    fn.write_text(json.dumps({"channel":channel,"text":text,"dry":dry}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(fn), "dry": dry}
