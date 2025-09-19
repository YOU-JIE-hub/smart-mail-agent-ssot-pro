from __future__ import annotations
import os, time, pathlib, json
def create_ticket(subject:str, body:str, tags=None, severity:str="P3", out_dir="reports_auto/actions/tickets"):
    dry = os.environ.get("SMA_DRY_RUN","1")!="0"
    od=pathlib.Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    fn=od/f"{time.strftime('%Y%m%dT%H%M%S')}_{severity}.json"
    fn.write_text(json.dumps({"subject":subject,"body":body,"tags":tags or [],"severity":severity,"dry":dry}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(fn), "dry": dry, "id": fn.stem}
