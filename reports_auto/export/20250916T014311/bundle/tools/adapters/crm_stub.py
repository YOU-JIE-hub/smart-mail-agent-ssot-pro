from __future__ import annotations
import os, time, pathlib, json
def upsert_deal(title:str, total:int, meta:dict=None, out_dir="reports_auto/actions/crm"):
    dry = os.environ.get("SMA_DRY_RUN","1")!="0"
    od=pathlib.Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    fn=od/f"{time.strftime('%Y%m%dT%H%M%S')}.json"
    fn.write_text(json.dumps({"title":title,"total":total,"meta":meta or {},"dry":dry}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(fn), "dry": dry, "deal_id": fn.stem}
