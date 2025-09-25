import os, json, pathlib, csv, math
from pathlib import Path
import numpy as np, joblib
from sklearn.metrics import accuracy_score, f1_score

root=Path("."); out=(root/"reports_auto/pro/latest"); out.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    p=Path(p); rows=[]
    if p.exists():
        for ln in p.read_text("utf-8").splitlines():
            ln=ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except: pass
    return rows

def get_proba(m, X):
    # returns np.ndarray of shape (n, n_classes) or None
    if hasattr(m, "predict_proba"):
        try:
            return m.predict_proba(X)
        except Exception:
            pass
    if hasattr(m, "decision_function"):
        try:
            df=m.decision_function(X)
            a=np.asarray(df)
            if a.ndim==1:
                # binary to two-column
                a=np.vstack([-a, a]).T
            # temperature-free softmax as pseudo probas
            e=np.exp(a - a.max(axis=1, keepdims=True))
            p=e / e.sum(axis=1, keepdims=True)
            return p
        except Exception:
            pass
    return None

def dump_errors(name, model_env, data_path, label_key="label", topk=3):
    pkl=os.environ.get(model_env,""); p=Path(pkl)
    rows=read_jsonl(data_path)
    X=[r.get("text","") for r in rows]
    y=[r.get(label_key, 0) for r in rows]
    if name=="spam": y=[int(v) for v in y]
    out_tsv=out/f"errors_{name}.tsv"
    if (not p.exists()) or (not X):
        out_tsv.write_text("", "utf-8"); return {"status":"skip","path":str(out_tsv)}
    m=joblib.load(p)
    y_pred=m.predict(X)
    proba=get_proba(m, X)
    classes=getattr(m, "classes_", None)
    with open(out_tsv, "w", newline="", encoding="utf-8") as f:
        w=csv.writer(f, delimiter="\t")
        hdr=["idx","text","y_true","y_pred","correct","confidence","topk_labels","topk_probs"]
        w.writerow(hdr)
        for i,(t,yt,yp) in enumerate(zip(X,y,y_pred)):
            conf=""
            topL=""; topP=""
            if proba is not None and classes is not None:
                row=proba[i]
                j=int(np.argmax(row))
                conf=str(float(row[j]))
                order=list(np.argsort(row))[::-1][:topk]
                topL="|".join([str(classes[k]) for k in order])
                topP="|".join([f"{float(row[k]):.4f}" for k in order])
            w.writerow([i, t.replace("\t"," ").replace("\n"," "), yt, yp, int(yp==yt), conf, topL, topP])
    return {"status":"ok","path":str(out_tsv)}

res={"intent": dump_errors("intent","INTENT_PKL", root/"data/intent_eval/test.jsonl", "label"),
     "spam":   dump_errors("spam","SPAM_PKL", root/"data/spam_eval/test.jsonl", "label")}
print(json.dumps(res, ensure_ascii=False, indent=2))
