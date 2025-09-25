import json, re
from pathlib import Path
import joblib
from sklearn.metrics import accuracy_score, f1_score
from runtime_preproc import normalize_text

def _nt(s, task):
    try:
        return normalize_text(s, task=task)
    except TypeError:
        return normalize_text(s)


root = Path("."); out = root/"reports_auto/pro/latest"; out.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    p = Path(p); rows=[]
    if p.exists():
        for ln in p.read_text("utf-8").splitlines():
            ln=ln.strip()
            if not ln: continue
            try: rows.append(json.loads(ln))
            except: pass
    return rows

def inject_url(s):
    # 若已有 URL 就原樣返回；否則加一個假的
    if re.search(r'https?://\S+|www\.\S+', s, flags=re.I): return s
    return (s + " http://example.com")

def eval_task(model_path, data_path, is_binary=False, X_transform=lambda x:x):
    rows = read_jsonl(data_path)
    if not rows: 
        return {"status":"no_data","n":0,"metrics":{}}
    X = [ X_transform(r["text"]) for r in rows ]
    y = [ r["label"] for r in rows ]
    m = joblib.load(model_path)
    yp = m.predict(X)
    met = {"accuracy": float(accuracy_score(y, yp))}
    if is_binary: met["f1"] = float(f1_score(y, yp))
    else:         met["macro_f1"] = float(f1_score(y, yp, average="macro"))
    return {"status":"ok","n":len(rows),"metrics":met}

cfg = json.loads((out/"summary.json").read_text("utf-8"))
intent_mp, intent_dp = cfg["intent"]["model_path"], cfg["intent"]["data_path"]
spam_mp,   spam_dp   = cfg["spam"]["model_path"],   cfg["spam"]["data_path"]

res = {"intent":{}, "spam":{}}

# --- INTENT：macro_f1
res["intent"]["baseline"]      = eval_task(intent_mp, intent_dp, is_binary=False, X_transform=lambda x:x)
res["intent"]["url_no_pre"]    = eval_task(intent_mp, intent_dp, is_binary=False, X_transform=lambda x:inject_url(x))
res["intent"]["url_with_pre"]  = eval_task(intent_mp, intent_dp, is_binary=False, X_transform=lambda x:_nt(inject_url(x), 'intent'))

# --- SPAM：accuracy / f1（二分類）
res["spam"]["baseline"]        = eval_task(spam_mp,   spam_dp,   is_binary=True,  X_transform=lambda x:x)
res["spam"]["url_no_pre"]      = eval_task(spam_mp,   spam_dp,   is_binary=True,  X_transform=lambda x:inject_url(x))
res["spam"]["url_with_pre"]    = eval_task(spam_mp,   spam_dp,   is_binary=True,  X_transform=lambda x:_nt(inject_url(x), 'intent'))

# 計算掉分 & 修復幅度
def drop(a,b,key): return float(a["metrics"][key] - b["metrics"][key])
def safe(d, path, key): 
    for p in path: d = d[p]
    return d["metrics"][key]

if res["intent"]["baseline"]["status"]=="ok":
    k="macro_f1"
    b = safe(res, ["intent","baseline"],     k)
    u = safe(res, ["intent","url_no_pre"],   k)
    p = safe(res, ["intent","url_with_pre"], k)
    res["intent"]["url_drop"] = float(b-u)
    res["intent"]["preproc_regain"] = float(p-u)

if res["spam"]["baseline"]["status"]=="ok":
    # 用 accuracy 觀察掉分，也保留 f1
    for k in ["accuracy","f1"]:
        b = safe(res, ["spam","baseline"],     k)
        u = safe(res, ["spam","url_no_pre"],   k)
        p = safe(res, ["spam","url_with_pre"], k)
        res["spam"][f"url_drop_{k}"] = float(b-u)
        res["spam"][f"preproc_regain_{k}"] = float(p-u)

(out/"robust_ab_url.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), "utf-8")
print("[OK] wrote", out/"robust_ab_url.json")
