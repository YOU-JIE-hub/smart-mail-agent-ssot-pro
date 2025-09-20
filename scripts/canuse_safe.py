import os, json, pathlib, random
from collections import Counter
from typing import Iterable, Tuple
from datetime import datetime

import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / f"reports_auto/train_rebuild_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

# 你機器上已確認存在且可用的兩份資料（從你前面貼的掃描結果來）
INTENT_CANDS = [
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    str(ROOT/"data/train.jsonl"),
]
SPAM_CANDS = [
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    str(ROOT/"data/spam_eval/dataset.jsonl"),
]

def pick_existing(cands):
    for p in cands:
        if pathlib.Path(p).exists(): return p
    return None

def iter_jsonl(path:str) -> Iterable[Tuple[str,str]]:
    import json
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            # label 常見鍵
            y = o.get("label") or o.get("y") or o.get("target") or o.get("tag")
            if y is None: continue
            # text 常見鍵；不行就把所有字串欄位拼起來
            x = o.get("text") or o.get("body") or o.get("content") or o.get("message") or o.get("subject")
            if not isinstance(x, str):
                x = " ".join([str(v) for k,v in o.items() if k!="label" and isinstance(v, str)])
            if x: yield x, str(y)

def train_one(in_path: str, out_pkl: pathlib.Path):
    rows = list(iter_jsonl(in_path))
    if not rows: raise RuntimeError(f"no rows parsed from {in_path}")
    X, y = zip(*rows)
    cnt = Counter(y)
    if len(cnt) < 2:
        raise RuntimeError(f"only one class in {in_path}: {cnt}")
    # 取樣避免超大
    if len(X) > 20000:
        idx = list(range(len(X)))
        random.Random(0).shuffle(idx)
        idx = idx[:20000]
        X = [X[i] for i in idx]; y = [y[i] for i in idx]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=200000, ngram_range=(1,2))),
        ("lr", LogisticRegression(max_iter=2000, n_jobs=None, class_weight="balanced")),
    ])
    pipe.fit(Xtr, ytr)
    rep = classification_report(yte, pipe.predict(Xte), output_dict=True, zero_division=0)
    out_pkl.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out_pkl)
    return rep

def main():
    intent_path = pick_existing(INTENT_CANDS)
    spam_path   = pick_existing(SPAM_CANDS)
    if not intent_path:
        raise SystemExit("no intent dataset found")
    if not spam_path:
        raise SystemExit("no spam dataset found")

    rep_intent = train_one(intent_path, ROOT/"models/intent/artifacts/model_pipeline.pkl")
    rep_spam   = train_one(spam_path,   ROOT/"models/spam/artifacts/model_pipeline.pkl")

    envp = OUT/"MODEL_PATHS.auto.env"
    envp.write_text(
        'INTENT_PKL="'+str((ROOT/"models/intent/artifacts/model_pipeline.pkl").resolve())+'"\n'
        'SPAM_PKL="'+str((ROOT/"models/spam/artifacts/model_pipeline.pkl").resolve())+'"\n',
        encoding="utf-8"
    )
    (OUT/"report.json").write_text(json.dumps({
        "datasets": {"intent": intent_path, "spam": spam_path},
        "reports": {"intent": rep_intent, "spam": rep_spam}
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[use] intent: {intent_path}")
    print(f"[use] spam  : {spam_path}")
    print(f"[out] env  : {envp}")
    print(f"[out] pkl  : models/intent/artifacts/model_pipeline.pkl ; models/spam/artifacts/model_pipeline.pkl")
    print(f"[out] rep  : {OUT/'report.json'}")

if __name__ == "__main__":
    main()
