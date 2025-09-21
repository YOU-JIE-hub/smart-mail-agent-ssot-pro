+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\'' 
import os, json, time, pathlib, joblib
from sklearn.metrics import classification_report, accuracy_score

root = pathlib.Path(".").resolve()
reports = root/"reports_auto"; reports.mkdir(parents=True, exist_ok=True)

def load_jsonl(p):
    p = pathlib.Path(p)
    if not p.exists(): return [], f"path_missing: {p}"
    rows=[]
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: rows.append(json.loads(line))
            except Exception as e: return [], f"bad_jsonl: {p} -> {e}"
    return rows, None

def eval_clf(task, pkl_env, data_path):
    out={"task":task, "model_path":os.environ.get(pkl_env), "data_path":str(data_path)}
    mp = os.environ.get(pkl_env)
    if not mp: out.update(status="error", error=f"{pkl_env}_missing"); return out
    mp = pathlib.Path(mp).expanduser().resolve()
    if not mp.exists():
        out.update(status="error", error=f"model_not_found: {mp}"); return out
    # 讓舊 pkl 可讀（__main__.rules_feat*）
    try:
        import tools.compat_loader  # noqa: F401
    except Exception:
        pass
    try:
        clf = joblib.load(mp)
    except Exception as e:
        out.update(status="error", error=f"joblib_load_failed: {e}"); return out
    rows, err = load_jsonl(data_path)
    if err: out.update(status="error", error=err); return out
    X = [r.get("text","") for r in rows]
    y_true = [r.get("label") for r in rows] if rows and "label" in rows[0] else None
    try:
        y_pred = clf.predict(X)
    except Exception as e:
        out.update(status="error", error=f"predict_failed: {e}", n=len(X)); return out
    out.update(status="ok", n=len(X), classes_=list(getattr(clf,"classes_",[])))
    if y_true is not None and all(v is not None for v in y_true):
        try:
            rep = classification_report(y_true, y_pred, zero_division=0, output_dict=True)
            out["metrics"] = {
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "macro_f1": float(rep.get("macro avg",{}).get("f1-score",0.0)),
                "per_class": {str(k): v for k,v in rep.items() if k not in ("accuracy","macro avg","weighted avg")}
            }
        except Exception as e:
            out["metrics_error"] = f"classification_report_failed: {e}"
    else:
        out["sample_pred"] = list(map(lambda x: x if isinstance(x, (str,int,float)) else str(x), y_pred[:10]))
    return out

def check_kie():
    d = os.environ.get("KIE_DIR")
    out={"task":"kie", "dir":d}
    if not d: out.update(status="error", error="KIE_DIR_missing"); return out
    p = pathlib.Path(d).expanduser().resolve()
    if not p.exists(): out.update(status="error", error=f"kie_dir_not_found: {p}"); return out
    req = ["config.json","model.safetensors","tokenizer.json"]
    exist = {f: (p/f).exists() for f in req}
    out.update(status="ok" if all(exist.values()) else "warn", files=exist)
    return out

summary = {
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "intent": eval_clf("intent","INTENT_PKL", root/"data/intent_eval/test.jsonl"),
    "spam":   eval_clf("spam","SPAM_PKL",   root/"data/spam_eval/test.jsonl"),
    "kie":    check_kie(),
}

outp = reports/"summary.json"
outp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
print((outp).read_text(encoding="utf-8")[:2000])
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\'' 
import os, json, time, pathlib, joblib
from sklearn.metrics import classification_report, accuracy_score

root = pathlib.Path(".").resolve()
reports = root/"reports_auto"; reports.mkdir(parents=True, exist_ok=True)

def load_jsonl(p):
    p = pathlib.Path(p)
    if not p.exists(): return [], f"path_missing: {p}"
    rows=[]
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: rows.append(json.loads(line))
            except Exception as e: return [], f"bad_jsonl: {p} -> {e}"
    return rows, None

def eval_clf(task, pkl_env, data_path):
    out={"task":task, "model_path":os.environ.get(pkl_env), "data_path":str(data_path)}
    mp = os.environ.get(pkl_env)
    if not mp: out.update(status="error", error=f"{pkl_env}_missing"); return out
    mp = pathlib.Path(mp).expanduser().resolve()
    if not mp.exists():
        out.update(status="error", error=f"model_not_found: {mp}"); return out
    # 讓舊 pkl 可讀（__main__.rules_feat*）
    try:
        import tools.compat_loader  # noqa: F401
    except Exception:
        pass
    try:
        clf = joblib.load(mp)
    except Exception as e:
        out.update(status="error", error=f"joblib_load_failed: {e}"); return out
    rows, err = load_jsonl(data_path)
    if err: out.update(status="error", error=err); return out
    X = [r.get("text","") for r in rows]
    y_true = [r.get("label") for r in rows] if rows and "label" in rows[0] else None
    try:
        y_pred = clf.predict(X)
    except Exception as e:
        out.update(status="error", error=f"predict_failed: {e}", n=len(X)); return out
    out.update(status="ok", n=len(X), classes_=list(getattr(clf,"classes_",[])))
    if y_true is not None and all(v is not None for v in y_true):
        try:
            rep = classification_report(y_true, y_pred, zero_division=0, output_dict=True)
            out["metrics"] = {
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "macro_f1": float(rep.get("macro avg",{}).get("f1-score",0.0)),
                "per_class": {str(k): v for k,v in rep.items() if k not in ("accuracy","macro avg","weighted avg")}
            }
        except Exception as e:
            out["metrics_error"] = f"classification_report_failed: {e}"
    else:
        out["sample_pred"] = list(map(lambda x: x if isinstance(x, (str,int,float)) else str(x), y_pred[:10]))
    return out

def check_kie():
    d = os.environ.get("KIE_DIR")
    out={"task":"kie", "dir":d}
    if not d: out.update(status="error", error="KIE_DIR_missing"); return out
    p = pathlib.Path(d).expanduser().resolve()
    if not p.exists(): out.update(status="error", error=f"kie_dir_not_found: {p}"); return out
    req = ["config.json","model.safetensors","tokenizer.json"]
    exist = {f: (p/f).exists() for f in req}
    out.update(status="ok" if all(exist.values()) else "warn", files=exist)
    return out

summary = {
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "intent": eval_clf("intent","INTENT_PKL", root/"data/intent_eval/test.jsonl"),
    "spam":   eval_clf("spam","SPAM_PKL",   root/"data/spam_eval/test.jsonl"),
    "kie":    check_kie(),
}

outp = reports/"summary.json"
outp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
print((outp).read_text(encoding="utf-8")[:2000])
PY' ']'
+ echo '== SNAPSHOT 20250921T115801 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT|SPAM|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc '. .venv/bin/activate; python3 - <<'\''PY'\'' 
import os, json, time, pathlib, joblib
from sklearn.metrics import classification_report, accuracy_score

root = pathlib.Path(".").resolve()
reports = root/"reports_auto"; reports.mkdir(parents=True, exist_ok=True)

def load_jsonl(p):
    p = pathlib.Path(p)
    if not p.exists(): return [], f"path_missing: {p}"
    rows=[]
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: rows.append(json.loads(line))
            except Exception as e: return [], f"bad_jsonl: {p} -> {e}"
    return rows, None

def eval_clf(task, pkl_env, data_path):
    out={"task":task, "model_path":os.environ.get(pkl_env), "data_path":str(data_path)}
    mp = os.environ.get(pkl_env)
    if not mp: out.update(status="error", error=f"{pkl_env}_missing"); return out
    mp = pathlib.Path(mp).expanduser().resolve()
    if not mp.exists():
        out.update(status="error", error=f"model_not_found: {mp}"); return out
    # 讓舊 pkl 可讀（__main__.rules_feat*）
    try:
        import tools.compat_loader  # noqa: F401
    except Exception:
        pass
    try:
        clf = joblib.load(mp)
    except Exception as e:
        out.update(status="error", error=f"joblib_load_failed: {e}"); return out
    rows, err = load_jsonl(data_path)
    if err: out.update(status="error", error=err); return out
    X = [r.get("text","") for r in rows]
    y_true = [r.get("label") for r in rows] if rows and "label" in rows[0] else None
    try:
        y_pred = clf.predict(X)
    except Exception as e:
        out.update(status="error", error=f"predict_failed: {e}", n=len(X)); return out
    out.update(status="ok", n=len(X), classes_=list(getattr(clf,"classes_",[])))
    if y_true is not None and all(v is not None for v in y_true):
        try:
            rep = classification_report(y_true, y_pred, zero_division=0, output_dict=True)
            out["metrics"] = {
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "macro_f1": float(rep.get("macro avg",{}).get("f1-score",0.0)),
                "per_class": {str(k): v for k,v in rep.items() if k not in ("accuracy","macro avg","weighted avg")}
            }
        except Exception as e:
            out["metrics_error"] = f"classification_report_failed: {e}"
    else:
        out["sample_pred"] = list(map(lambda x: x if isinstance(x, (str,int,float)) else str(x), y_pred[:10]))
    return out

def check_kie():
    d = os.environ.get("KIE_DIR")
    out={"task":"kie", "dir":d}
    if not d: out.update(status="error", error="KIE_DIR_missing"); return out
    p = pathlib.Path(d).expanduser().resolve()
    if not p.exists(): out.update(status="error", error=f"kie_dir_not_found: {p}"); return out
    req = ["config.json","model.safetensors","tokenizer.json"]
    exist = {f: (p/f).exists() for f in req}
    out.update(status="ok" if all(exist.values()) else "warn", files=exist)
    return out

summary = {
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "intent": eval_clf("intent","INTENT_PKL", root/"data/intent_eval/test.jsonl"),
    "spam":   eval_clf("spam","SPAM_PKL",   root/"data/spam_eval/test.jsonl"),
    "kie":    check_kie(),
}

outp = reports/"summary.json"
outp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
print((outp).read_text(encoding="utf-8")[:2000])
PY'
++ tee -a reports_auto/panic_20250921T115801/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<'\''PY'\'' 
import os, json, time, pathlib, joblib
from sklearn.metrics import classification_report, accuracy_score

root = pathlib.Path(".").resolve()
reports = root/"reports_auto"; reports.mkdir(parents=True, exist_ok=True)

def load_jsonl(p):
    p = pathlib.Path(p)
    if not p.exists(): return [], f"path_missing: {p}"
    rows=[]
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: rows.append(json.loads(line))
            except Exception as e: return [], f"bad_jsonl: {p} -> {e}"
    return rows, None

def eval_clf(task, pkl_env, data_path):
    out={"task":task, "model_path":os.environ.get(pkl_env), "data_path":str(data_path)}
    mp = os.environ.get(pkl_env)
    if not mp: out.update(status="error", error=f"{pkl_env}_missing"); return out
    mp = pathlib.Path(mp).expanduser().resolve()
    if not mp.exists():
        out.update(status="error", error=f"model_not_found: {mp}"); return out
    # 讓舊 pkl 可讀（__main__.rules_feat*）
    try:
        import tools.compat_loader  # noqa: F401
    except Exception:
        pass
    try:
        clf = joblib.load(mp)
    except Exception as e:
        out.update(status="error", error=f"joblib_load_failed: {e}"); return out
    rows, err = load_jsonl(data_path)
    if err: out.update(status="error", error=err); return out
    X = [r.get("text","") for r in rows]
    y_true = [r.get("label") for r in rows] if rows and "label" in rows[0] else None
    try:
        y_pred = clf.predict(X)
    except Exception as e:
        out.update(status="error", error=f"predict_failed: {e}", n=len(X)); return out
    out.update(status="ok", n=len(X), classes_=list(getattr(clf,"classes_",[])))
    if y_true is not None and all(v is not None for v in y_true):
        try:
            rep = classification_report(y_true, y_pred, zero_division=0, output_dict=True)
            out["metrics"] = {
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "macro_f1": float(rep.get("macro avg",{}).get("f1-score",0.0)),
                "per_class": {str(k): v for k,v in rep.items() if k not in ("accuracy","macro avg","weighted avg")}
            }
        except Exception as e:
            out["metrics_error"] = f"classification_report_failed: {e}"
    else:
        out["sample_pred"] = list(map(lambda x: x if isinstance(x, (str,int,float)) else str(x), y_pred[:10]))
    return out

def check_kie():
    d = os.environ.get("KIE_DIR")
    out={"task":"kie", "dir":d}
    if not d: out.update(status="error", error="KIE_DIR_missing"); return out
    p = pathlib.Path(d).expanduser().resolve()
    if not p.exists(): out.update(status="error", error=f"kie_dir_not_found: {p}"); return out
    req = ["config.json","model.safetensors","tokenizer.json"]
    exist = {f: (p/f).exists() for f in req}
    out.update(status="ok" if all(exist.values()) else "warn", files=exist)
    return out

summary = {
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "intent": eval_clf("intent","INTENT_PKL", root/"data/intent_eval/test.jsonl"),
    "spam":   eval_clf("spam","SPAM_PKL",   root/"data/spam_eval/test.jsonl"),
    "kie":    check_kie(),
}

outp = reports/"summary.json"
outp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
print((outp).read_text(encoding="utf-8")[:2000])
PY'
+ echo '- LOG  : reports_auto/panic_20250921T115801/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T115801/run.err'
+ echo '- PY   : reports_auto/panic_20250921T115801/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T115801/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T115801/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T115801/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T115801/run.err reports_auto/panic_20250921T115801/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T115801/run.err reports_auto/panic_20250921T115801/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T115801/run.err reports_auto/panic_20250921T115801/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T115801/run.err reports_auto/panic_20250921T115801/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T115801/REPORT.md\nreports_auto/panic_20250921T115801/run.log\nreports_auto/panic_20250921T115801/run.err\nreports_auto/panic_20250921T115801/python_stderr.txt\nreports_auto/panic_20250921T115801/xtrace.sh\nreports_auto/panic_20250921T115801/system.txt\nreports_auto/panic_20250921T115801/oom.txt\n'
+ exit 1
