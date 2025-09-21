# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY' 
import os, json, time, hashlib, pathlib, joblib
def py(obj):
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.ndarray,)): return obj.tolist()
    except Exception: pass
    if isinstance(obj, (set,)): return list(obj)
    try:
        # 小心 classes_ 可能是 numpy array
        import numpy as np
        if "classes_" in str(obj.__class__): 
            return list(obj)
    except Exception: pass
    return str(obj)

def provenance_of(pkl_path):
    p=pathlib.Path(pkl_path).expanduser().resolve()
    d={"path": str(p), "exists": p.exists(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not p.exists(): return d
    b=p.read_bytes()
    d.update({"size_bytes": int(len(b)), "sha256": hashlib.sha256(b).hexdigest()})
    try:
        m=joblib.load(p)
        d["classes_"]=list(getattr(m,"classes_", []))
        d["sklearn_pipeline"]=type(m).__name__
    except Exception as e:
        d["load_error"]=str(e)
    (p.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2, default=py), "utf-8")
    return d

prov={}
if os.environ.get("INTENT_PKL"): prov["intent"]=provenance_of(os.environ["INTENT_PKL"])
if os.environ.get("SPAM_PKL"):   prov["spam"]=provenance_of(os.environ["SPAM_PKL"])
print(json.dumps(prov, ensure_ascii=False, indent=2, default=py))
PY
- LOG  : reports_auto/panic_20250921T114555/run.log
- ERR  : reports_auto/panic_20250921T114555/run.err
- PY   : reports_auto/panic_20250921T114555/python_stderr.txt
- OOM  : reports_auto/panic_20250921T114555/oom.txt
- TRACE: reports_auto/panic_20250921T114555/xtrace.sh
- SYS  : reports_auto/panic_20250921T114555/system.txt

## Heuristics
