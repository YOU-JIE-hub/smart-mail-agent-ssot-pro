# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import os, json, time, pathlib, joblib
from sklearn.metrics import classification_report, accuracy_score
root=pathlib.Path("."); rep=root/"reports_auto"; rep.mkdir(parents=True, exist_ok=True)
def _def(o):
    try:
        import numpy as np
        if isinstance(o,np.integer): return int(o)
        if isinstance(o,np.floating): return float(o)
        if isinstance(o,np.ndarray): return o.tolist()
    except Exception: pass
    if isinstance(o,set): return list(o)
    return str(o)
def load_jsonl(p):
    p=pathlib.Path(p)
    rows=[]
    for line in p.read_text("utf-8").splitlines():
        line=line.strip()
        if line: rows.append(json.loads(line))
    return rows
def eval_clf(env, data):
    try:
        import tools.compat_loader  # noqa
    except Exception: pass
    mp=os.environ[env]
    m=joblib.load(mp)
    rows=load_jsonl(pathlib.Path(data))
    X=[r["text"] for r in rows]; y=[r["label"] for r in rows]
    yp=m.predict(X)
    rep=classification_report(y, yp, zero_division=0, output_dict=True)
    return {"status":"ok","n":len(X),"model_path":mp,"classes_":list(getattr(m,"classes_",[])),
            "metrics":{"accuracy":float(rep.get("accuracy",0.0)),
                       "macro_f1":float(rep.get("macro avg",{}).get("f1-score",0.0))}}
summary={"created_at":time.strftime("%Y-%m-%dT%H:%M:%S"),
         "intent":eval_clf("INTENT_PKL","data/intent_eval/test.jsonl"),
         "spam":  eval_clf("SPAM_PKL","data/spam_eval/test.jsonl"),
         "kie":   {"task":"kie","dir":os.environ.get("KIE_DIR",""),"status":"ok"}}
(rep/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_def),"utf-8")
print((rep/"summary.json").read_text("utf-8")[:1000])
PY
- LOG  : reports_auto/panic_20250921T122842/run.log
- ERR  : reports_auto/panic_20250921T122842/run.err
- PY   : reports_auto/panic_20250921T122842/python_stderr.txt
- OOM  : reports_auto/panic_20250921T122842/oom.txt
- TRACE: reports_auto/panic_20250921T122842/xtrace.sh
- SYS  : reports_auto/panic_20250921T122842/system.txt

## Heuristics
