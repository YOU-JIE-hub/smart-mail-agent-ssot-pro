# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY' 
import os, json, time, hashlib, pathlib, joblib
def _def(o):
    try:
        import numpy as np
        if isinstance(o,np.integer): return int(o)
        if isinstance(o,np.floating): return float(o)
        if isinstance(o,np.ndarray): return o.tolist()
    except Exception: pass
    if isinstance(o,set): return list(o)
    return str(o)

def provenance_of(p):
    p=pathlib.Path(p).expanduser().resolve()
    d={"path":str(p),"exists":p.exists(),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not p.exists(): return d
    b=p.read_bytes()
    d.update({"size_bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()})
    try:
        import tools.compat_loader  # noqa
        m=joblib.load(p)
        d["classes_"]=list(getattr(m,"classes_",[]))
        d["sklearn_pipeline"]=type(m).__name__
    except Exception as e:
        d["load_error"]=str(e)
    (p.parent/"PROVENANCE.json").write_text(json.dumps(d,ensure_ascii=False,indent=2,default=_def),"utf-8")
    return d

out={}
if os.environ.get("INTENT_PKL"): out["intent"]=provenance_of(os.environ["INTENT_PKL"])
if os.environ.get("SPAM_PKL"):   out["spam"]=provenance_of(os.environ["SPAM_PKL"])

kie=os.environ.get("KIE_DIR"); k={}
if kie:
    d=pathlib.Path(kie).expanduser().resolve()
    k={"dir":str(d),"exists":d.exists()}
    need=["config.json","model.safetensors","tokenizer.json"]
    k["files"]={n:(d/n).exists() for n in need}
out["kie_check"]=k
(pathlib.Path("reports_auto")/"provenance_summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,default=_def),"utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2, default=_def))
PY
- LOG  : reports_auto/panic_20250921T122432/run.log
- ERR  : reports_auto/panic_20250921T122432/run.err
- PY   : reports_auto/panic_20250921T122432/python_stderr.txt
- OOM  : reports_auto/panic_20250921T122432/oom.txt
- TRACE: reports_auto/panic_20250921T122432/xtrace.sh
- SYS  : reports_auto/panic_20250921T122432/system.txt

## Heuristics
