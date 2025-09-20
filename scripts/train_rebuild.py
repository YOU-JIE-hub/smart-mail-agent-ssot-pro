import os, json, re, sys, time, math, hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter

import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / f"reports_auto/train_rebuild_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
(OUTDIR).mkdir(parents=True, exist_ok=True)

# 你環境裡已經掃到的兩份資料（先用它們，找不到再兜底到 repo 內 data/*）
CANDIDATES = [
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",               # intent/ham-spam 二分類
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",         # spam 二分類
]

def is_jsonl(p: Path) -> bool:
    return p.suffix == ".jsonl" and p.is_file()

def read_jsonl_guess_xy(p: Path):
    X, y = [], []
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                obj=json.loads(line)
            except Exception:
                # 兜底：若不是合法 json，就當純文字，標成 ham
                X.append(line); y.append("ham"); continue
            # 常見欄位兜底
            txt = obj.get("text") or obj.get("content") or obj.get("body") or ""
            lab = obj.get("label") or obj.get("tag") or obj.get("y") or obj.get("class")
            # 有些數字標籤：0/1 -> ham/spam
            if isinstance(lab, (int, float)):
                lab = "spam" if int(lab)==1 else "ham"
            if lab is None: lab = "ham"
            X.append(str(txt)); y.append(str(lab))
    return X, y

def choose_files():
    hits=[]
    # 先試固定清單
    for s in CANDIDATES:
        p=Path(s); ifok=is_jsonl(p); 
        if ifok: hits.append(p)
    # 再補掃 repo 內較像資料的檔
    for p in (ROOT/"data").rglob("*.jsonl"):
        if is_jsonl(p) and p not in hits:
            hits.append(p)
    return hits

def train_one(name:str, X, y, out_pkl:Path):
    # 移除空字串
    data=[(tx,lb) for tx,lb in zip(X,y) if tx and tx.strip()]
    if not data: raise RuntimeError(f"{name}: empty dataset after cleaning")
    X=[t for t,_ in data]; y=[l for _,l in data]
    cnt=Counter(y)
    if len(cnt)<2:
        raise RuntimeError(f"{name}: single-class dataset {dict(cnt)}")

    Xtr, Xte, ytr, yte = train_test_split(X,y, test_size=0.2, random_state=42, stratify=y)
    # 向量器 + LR（避免 Calibrated + SVC 在某些折出現單類）
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=2, max_df=0.95)),
        ("clf",   LogisticRegression(max_iter=1000, n_jobs=None, class_weight="balanced"))
    ])
    pipe.fit(Xtr, ytr)
    rep = classification_report(yte, pipe.predict(Xte), output_dict=True, zero_division=0)

    out_pkl.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out_pkl)
    return rep

def main():
    files=choose_files()
    # intent/ spam 以 label 分佈猜測：有 "spam"/"ham" 就可兩邊共用；我們各自訓兩份 pipeline
    # 找到第一個可用的檔當 intent，第二個（不同路徑）當 spam；若只找到一份也先訓起來
    chosen=[]
    for p in files:
        try:
            X,y = read_jsonl_guess_xy(p)
            if len(X) >= 200 and len(set(y))>=2:
                chosen.append((p, Counter(y)))
        except Exception: 
            continue
        if len(chosen)>=2: break

    if not chosen:
        raise SystemExit("no usable .jsonl found")

    # intent
    intent_src = chosen[0][0]
    rep_intent = train_one("intent", *read_jsonl_guess_xy(intent_src), ROOT/"models/intent/artifacts/model_pipeline.pkl")

    # spam（盡量選不同檔；沒有就重複那一份也可行）
    spam_src = chosen[1][0] if len(chosen)>1 else chosen[0][0]
    rep_spam   = train_one("spam",   *read_jsonl_guess_xy(spam_src  ), ROOT/"models/spam/artifacts/model_pipeline.pkl")

    env_path = OUTDIR/"MODEL_PATHS.auto.env"
    env_path.write_text(
        "INTENT_PKL=models/intent/artifacts/model_pipeline.pkl\n"
        "SPAM_PKL=models/spam/artifacts/model_pipeline.pkl\n",
        encoding="utf-8"
    )
    (OUTDIR/"report.json").write_text(json.dumps({
        "intent":{"src":str(intent_src),"report":rep_intent},
        "spam"  :{"src":str(spam_src),  "report":rep_spam}
    }, ensure_ascii=False, indent=2), "utf-8")

    print("[use] intent:", intent_src)
    print("[use] spam  :", spam_src)
    print("[out] env  :", env_path)
    print("[out] pkl  : models/intent/artifacts/model_pipeline.pkl ; models/spam/artifacts/model_pipeline.pkl")
    print("[out] rep  :", OUTDIR/"report.json")

if __name__=="__main__":
    main()
