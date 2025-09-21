# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import os, json, pathlib, numpy as np, joblib
from sklearn.metrics import f1_score, accuracy_score

root=pathlib.Path(".")
sjp=root/"reports_auto/summary.json"
j=json.loads(sjp.read_text("utf-8"))

def load_jsonl(p):
    P=pathlib.Path(p)
    rows=[]
    if not P.exists(): return rows
    for ln in P.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        rows.append(json.loads(ln))
    return rows

def to_py(x):
    if isinstance(x, (np.generic,)): return x.item()
    if isinstance(x, (list, tuple)): return [to_py(v) for v in x]
    if isinstance(x, dict): return {k:to_py(v) for k,v in x.items()}
    return x

# --- Intent：信心覆蓋曲線 ---
try:
    ip=os.environ.get("INTENT_PKL"); mp=os.environ.get("SPAM_PKL")
    intent = j.get("intent",{}); spam=j.get("spam",{})
    X_int=[r["text"] for r in load_jsonl(intent.get("data_path","data/intent_eval/test.jsonl"))]
    y_int=[r["label"] for r in load_jsonl(intent.get("data_path","data/intent_eval/test.jsonl"))]
    if ip and pathlib.Path(ip).exists() and X_int:
        m=joblib.load(ip)
        y_pred=m.predict(X_int)
        try:
            proba=m.predict_proba(X_int)
            conf=proba.max(axis=1)
        except Exception:
            conf=np.ones(len(y_pred),dtype=float)
        thr=[0.50,0.60,0.70,0.80,0.90]
        table=[]
        for t in thr:
            mask=conf>=t
            cov=float(mask.mean()) if len(mask)>0 else 0.0
            if cov>0:
                acc=float(accuracy_score(y_int, y_pred, sample_weight=mask.astype(float)))
                risk=float(1.0-acc)
            else:
                acc=0.0; risk=0.0
            table.append({"threshold":t,"coverage":cov,"accuracy":acc,"risk":risk})
        # 推薦門檻：風險<=10% 的最小 t；否則 coverage 最大的 t
        cand=[r for r in table if r["risk"]<=0.10 and r["coverage"]>0]
        rec=min(cand, key=lambda r:r["threshold"]) if cand else max(table, key=lambda r:r["coverage"])
        intent["thresholding"]={"confidence_curve":to_py(table),"recommended":to_py(rec)}
        j["intent"]=intent
except Exception as e:
    j.setdefault("intent",{}).setdefault("thresholding",{})["error"]=str(e)

# --- Spam：最佳閾值掃描（正類=1） ---
try:
    X_sp=[r["text"] for r in load_jsonl(spam.get("data_path","data/spam_eval/test.jsonl"))]
    y_sp=[int(r["label"]) for r in load_jsonl(spam.get("data_path","data/spam_eval/test.jsonl"))]
    if mp and pathlib.Path(mp).exists() and X_sp:
        m=joblib.load(mp)
        try:
            proba=m.predict_proba(X_sp)
            idx=list(m.classes_).index(1)
            p1=proba[:,idx]
        except Exception:
            # 無 predict_proba 就以 0/1 當置信度
            p1=(m.predict(X_sp)==1).astype(float)
        grid=np.linspace(0.1,0.9,17)
        best={"threshold":0.5,"f1":-1.0,"coverage":1.0}
        table=[]
        for t in grid:
            y_hat=(p1>=t).astype(int)
            f1=float(f1_score(y_sp, y_hat, zero_division=0))
            cov=float((p1>=t).mean())
            table.append({"threshold":float(t),"f1":f1,"coverage":cov})
            if f1>best["f1"]: best={"threshold":float(t),"f1":f1,"coverage":cov}
        spam["thresholding"]={"grid":to_py(table),"recommended":to_py(best)}
        j["spam"]=spam
except Exception as e:
    j.setdefault("spam",{}).setdefault("thresholding",{})["error"]=str(e)

sjp.write_text(json.dumps(j, ensure_ascii=False, indent=2), "utf-8")
print("[OK] thresholds merged into summary.json")
PY
- LOG  : reports_auto/panic_20250921T134015/run.log
- ERR  : reports_auto/panic_20250921T134015/run.err
- PY   : reports_auto/panic_20250921T134015/python_stderr.txt
- OOM  : reports_auto/panic_20250921T134015/oom.txt
- TRACE: reports_auto/panic_20250921T134015/xtrace.sh
- SYS  : reports_auto/panic_20250921T134015/system.txt

## Heuristics
