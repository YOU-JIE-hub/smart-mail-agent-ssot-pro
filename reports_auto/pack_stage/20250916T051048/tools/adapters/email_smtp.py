from __future__ import annotations
import os, time, pathlib
def send_email(subject:str, body:str, to:str, out_dir="reports_auto/actions/email"):
    dry = os.environ.get("SMA_DRY_RUN","1")!="0"
    od = pathlib.Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    fn = od / f"{time.strftime('%Y%m%dT%H%M%S')}.eml"
    content = f"To: {to}\\nFrom: noreply@example.com\\nSubject: {subject}\\n\\n{body}\\n"
    fn.write_text(content, encoding="utf-8")
    return {"path": str(fn), "dry": dry}
