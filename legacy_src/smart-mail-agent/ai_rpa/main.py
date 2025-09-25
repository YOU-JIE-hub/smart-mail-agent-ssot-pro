from __future__ import annotations
import argparse, sys, json
from pathlib import Path
from . import nlp as _nlp
from . import actions_router as _router
def _read_text(p: str|None, use_stdin: bool=False) -> str:
    if use_stdin: return sys.stdin.read()
    if not p: return ""
    f=Path(p); 
    try: return f.read_text(encoding="utf-8", errors="ignore")
    except Exception: return ""
def main(argv=None)->int:
    ap=argparse.ArgumentParser(prog="sma")
    ap.add_argument("--input-path","--input",dest="input_path")
    ap.add_argument("--tasks", default="nlp,actions")
    ap.add_argument("--output","--out",dest="output")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--allow-online", action="store_true")
    ap.add_argument("--stdin", action="store_true")
    a=ap.parse_args(argv)
    text=_read_text(a.input_path, use_stdin=a.stdin)
    tasks=[t.strip() for t in (a.tasks or "").split(",") if t.strip()]
    out={}
    nlp_res=None
    if "nlp" in tasks:
        nlp_res=_nlp.analyze_text(text or "")
        out["nlp"]=nlp_res
    if "actions" in tasks:
        label=(nlp_res or {}).get("intent","other")
        routed=_router.route({"final":label})
        out["actions"]=[{"id":"sample","action":routed["action"],"label":label}]
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
