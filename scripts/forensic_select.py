import os, sys, json, re, random, hashlib, time
from pathlib import Path
from datetime import datetime
ROOTS = [
    Path("/home/youjie/projects/smart-mail-agent"),
    Path("/home/youjie/projects/smart-mail-agent_ssot"),
    Path("/home/youjie/projects/smart-mail-agent-ssot-pro"),
]
OUT = Path(os.environ.get("OUTDIR", "reports_auto/forensic_" + datetime.now().strftime("%Y%m%dT%H%M%S")))
OUT.mkdir(parents=True, exist_ok=True)
def jdump(obj, p): p = OUT/p; p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), "utf-8"); return p

# ---------- 相容載入 ----------
from importlib import import_module
sys.path.insert(0, str(Path.cwd()))
import tools.compat_loader as compat
compat.install()

import joblib
from collections import Counter
import io, gzip

def sha256_head(p, n=1024*1024):
    h=hashlib.sha256()
    with open(p,"rb") as f: h.update(f.read(n))
    return h.hexdigest()

def iter_lines(p, limit=None):
    if str(p).endswith(".gz"):
        f = gzip.open(p, "rt", encoding="utf-8", errors="ignore")
    else:
        f = open(p, "r", encoding="utf-8", errors="ignore")
    with f:
        for i,line in enumerate(f):
            if limit is not None and i>=limit: break
            yield line

def guess_records_from_jsonl(p, sample=3000):
    import json
    texts, labels = [], []
    for line in iter_lines(p, sample):
        try:
            j = json.loads(line)
        except Exception:
            continue
        # 嘗試抓 text/body/subject
        t = j.get("text") or j.get("body") or j.get("content") or j.get("subject")
        if not t: continue
        # 嘗試抓 label
        y = j.get("label", None)
        if y is None: 
            # 常見欄位別名
            for k in ("y","target","spam","is_spam","class","category"):
                if k in j: y = j[k]; break
        if isinstance(y, bool): y = "spam" if y else "ham"
        if isinstance(y, (int,float)):
            y = int(y)
            y = "spam" if y==1 else ("ham" if y==0 else str(y))
        if isinstance(y, str): 
            y = y.strip().lower()
        else:
            y = None
        texts.append(t)
        labels.append(y)
    return texts, labels

def score_model_on_dataset(pkl_path, ds_path, k=800):
    # 小樣本評分：隨機抽樣最多 k 筆且 label 非空
    import numpy as np
    try:
        clf = joblib.load(pkl_path)
    except Exception as e:
        return {"ok": False, "err": f"load:{e.__class__.__name__}: {e}"}
    X, y = guess_records_from_jsonl(ds_path, sample=5000)
    pairs = [(t,lab) for t,lab in zip(X,y) if lab in ("spam","ham")]
    if not pairs:
        return {"ok": False, "err": "dataset_no_binary_labels"}
    random.shuffle(pairs)
    pairs = pairs[:min(k, len(pairs))]
    Xs = [t for t,_ in pairs]; ys = [l for _,l in pairs]
    try:
        yp = clf.predict(Xs)
    except Exception as e:
        return {"ok": False, "err": f"predict:{e.__class__.__name__}: {e}"}
    ok = sum(1 for a,b in zip(ys,yp) if a==b)
    acc = ok/len(ys) if ys else 0.0
    from sklearn.metrics import classification_report
    rep = classification_report(ys, yp, output_dict=True, zero_division=0)
    return {"ok": True, "acc": acc, "report": rep, "n": len(ys)}

def list_candidates():
    model_pkls = []
    datasets = []
    ex_model = re.compile(r"(?:model_pipeline|text_lr|spam_.*model).*\.pkl$", re.I)
    for root in ROOTS:
        if not root.exists(): continue
        for p in root.rglob("*.pkl"):
            rel = p.as_posix()
            if ex_model.search(rel) and p.stat().st_size < 50*1024*1024:  # 避免超大檔
                model_pkls.append(p)
        for p in list(root.rglob("*.jsonl")) + list(root.rglob("*.jsonl.gz")):
            if p.stat().st_size >= 500_000:  # 至少 0.5MB 才像資料集
                datasets.append(p)
    # 排序：較新、較像目標路徑優先
    def mkey(p): 
        name = p.name
        score = 0
        if "model_pipeline" in name: score += 5
        if "spam" in p.as_posix(): score += 1
        if "intent" in p.as_posix(): score += 1
        return (-p.stat().st_mtime, -score)
    model_pkls.sort(key=mkey)
    datasets.sort(key=lambda p: -p.stat().st_mtime)
    return model_pkls, datasets

def pick_dataset_by_name_hint(datasets):
    # 根據你剛剛的記錄，優先這兩個
    hints = [
        "/smart-mail-agent/data/prod_merged/train.jsonl",
        "/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    ]
    for h in hints:
        for p in datasets:
            if h in p.as_posix():
                return p
    # 其次挑名字含 spam / eval / train 的
    for kw in ("spam_eval","train","dataset","spamassassin"):
        for p in datasets:
            if kw in p.as_posix():
                return p
    return datasets[0] if datasets else None

def quick_train(ds_path, out_pkl):
    from sklearn.pipeline import Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.calibration import CalibratedClassifierCV
    X, y = guess_records_from_jsonl(ds_path, sample=20000)
    pairs = [(t,lab) for t,lab in zip(X,y) if lab in ("spam","ham")]
    if not pairs:
        raise RuntimeError("dataset has no spam/ham labels")
    X = [t for t,_ in pairs]; y=[lab for _,lab in pairs]
    Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1,2), min_df=2, max_df=0.9)),
        ("clf", CalibratedClassifierCV(LogisticRegression(max_iter=2000, n_jobs=-1)))
    ])
    pipe.fit(Xtr,ytr)
    from sklearn.metrics import classification_report
    rep = classification_report(yte, pipe.predict(Xte), output_dict=True, zero_division=0)
    out_pkl.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out_pkl)
    return rep

def main():
    model_pkls, datasets = list_candidates()
    jdump({"models":[str(p) for p in model_pkls],
           "datasets":[str(p) for p in datasets]}, "CANDIDATES.json")
    chosen = {"intent":{}, "spam":{}}
    notes = []
    ds_pref_intent = pick_dataset_by_name_hint(datasets)  # 先用你最常提到的 train.jsonl
    ds_pref_spam   = None
    # 嘗試用可載入的 PKL + 可用資料集 評分
    for task in ("intent","spam"):
        best = None
        ds_path = ds_pref_intent if task=="intent" else (ds_pref_spam or ds_pref_intent)
        for pkl in model_pkls:
            p = pkl.as_posix().lower()
            if task=="spam" and "spam" not in p: 
                # 仍允許 generic model_pipeline 作為備援
                if "model_pipeline" not in p: 
                    continue
            if task=="intent" and "intent" not in p and "model_pipeline" not in p:
                continue
            res = score_model_on_dataset(pkl, ds_path) if ds_path else {"ok": False, "err":"no_dataset"}
            entry = {"pkl": pkl.as_posix(),
                     "size": pkl.stat().st_size,
                     "mtime": pkl.stat().st_mtime,
                     "sha256_head": sha256_head(pkl),
                     "dataset": ds_path.as_posix() if ds_path else None,
                     "probe": res}
            if res.get("ok"):
                acc = res.get("acc",0.0)
                if not best or acc > best["probe"].get("acc",0.0):
                    best = entry
            notes.append(entry)
        if best:
            chosen[task] = {"pkl": best["pkl"], "dataset": best["dataset"], "acc": best["probe"]["acc"]}
        else:
            # 沒有可用舊模型 → 用偏好的資料集快速重訓一份
            if not ds_path:
                chosen[task] = {"error":"no_dataset_found"}; continue
            out_pkl = Path("models")/task/"artifacts"/"model_pipeline.pkl"
            rep = quick_train(ds_path, out_pkl)
            chosen[task] = {"pkl": out_pkl.as_posix(), "dataset": ds_path.as_posix(), "acc": rep.get("accuracy",0.0), "trained": True, "report": rep}
    jdump(notes, "PROBES.json")
    selp = jdump(chosen, "SELECTION.json")
    # 寫 env
    env = OUT/"MODEL_PATHS.selected.env"
    lines=[]
    if "pkl" in chosen["intent"]: lines.append(f'INTENT_PKL="{chosen["intent"]["pkl"]}"')
    if "pkl" in chosen["spam"]:   lines.append(f'SPAM_PKL="{chosen["spam"]["pkl"]}"')
    env.write_text("\n".join(lines)+"\n","utf-8")
    # 煙霧測試
    smk = {}
    try:
        clf_i = joblib.load(chosen["intent"]["pkl"])
        smk["intent"] = clf_i.predict(["請問你們的客服電話？"])[0]
    except Exception as e:
        smk["intent_err"]=str(e)
    try:
        clf_s = joblib.load(chosen["spam"]["pkl"])
        smk["spam"] = clf_s.predict(["FREE $$$ click here!!!"])[0]
    except Exception as e:
        smk["spam_err"]=str(e)
    jdump(smk, "SMOKE.json")
    print("OUTDIR", OUT.as_posix())
if __name__=="__main__": main()
