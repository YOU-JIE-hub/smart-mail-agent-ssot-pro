from __future__ import annotations
import time, pathlib
def write_quote_txt(summary:str, out_dir="reports_auto/actions/quotes"):
    od=pathlib.Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    fn=od/f"{time.strftime('%Y%m%dT%H%M%S')}.txt"
    fn.write_text(summary, encoding="utf-8")
    return {"path": str(fn)}
