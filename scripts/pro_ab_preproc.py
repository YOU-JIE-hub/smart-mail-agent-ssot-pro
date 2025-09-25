import json, pathlib, joblib
from pathlib import Path
from runtime_preproc import normalize_text
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

def eval_task(model_path, data_path, is_binary=False, use_preproc=False):
    rows = read_jsonl(data_path)
    if not rows: return {"status":"no_data"}
    X = [ (normalize_text(r["text"]) if use_preproc else r["text"]) for r in rows ]
    y = [ r["label"] for r in rows ]
    m = joblib.load(model_path)
    yp = m.predict(X)
    from sklearn.metrics import accuracy_score, f1_score
    met={"accuracy": float(accuracy_score(y, yp))}
    if is_binary:
        met["f1"] = float(f1_score(y, yp))
    else:
        met["macro_f1"] = float(f1_score(y, yp, average="macro"))
    return {"n":len(rows),"metrics":met}

cfg = json.loads((root/"reports_auto/pro/latest/summary.json").read_text("utf-8"))
intent_mp = cfg["intent"]["model_path"]; intent_dp = cfg["intent"]["data_path"]
spam_mp   = cfg["spam"]["model_path"];   spam_dp   = cfg["spam"]["data_path"]

res = {"intent":{}, "spam":{}}
for use in [False, True]:
    tag = "preproc" if use else "raw"
    res["intent"][tag] = eval_task(intent_mp, intent_dp, is_binary=False, use_preproc=use)
    res["spam"][tag]   = eval_task(spam_mp,   spam_dp,   is_binary=True,  use_preproc=use)

(Path(out/"ab_preproc.json")).write_text(json.dumps(res, ensure_ascii=False, indent=2), "utf-8")
print("[OK] A/B saved:", out/"ab_preproc.json")
