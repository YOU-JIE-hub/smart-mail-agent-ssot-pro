from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import json, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
ART  = ROOT/"intent"/"artifacts_ml"
DATA = ROOT/"intent"/"data"
ART.mkdir(parents=True, exist_ok=True)

FALLBACK = [
    {"text":"想洽談合作與報價",       "label":"biz_quote"},
    {"text":"需要客服協助 無法登入",   "label":"tech_support"},
    {"text":"想了解退款機制與使用限制", "label":"policy_qa"},
    {"text":"我要更新地址與電話",       "label":"profile_update"},
    {"text":"很失望 客服回覆太慢",     "label":"complaint"},
    {"text":"哈囉 請問",               "label":"other"},
]

def _read_jsonl(p: Path) -> List[Dict]:
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

def _load_data() -> List[Dict]:
    xs = _read_jsonl(DATA/"train.jsonl")
    return xs if xs else FALLBACK

def train():
    rows = _load_data()
    X = [r["text"] for r in rows]
    y = [r["label"] for r in rows]
    labels = sorted(sorted(set(y)))  # deterministic order
    lab2id = {lab:i for i,lab in enumerate(labels)}
    y_id = [lab2id[v] for v in y]

    vec = TfidfVectorizer(ngram_range=(1,2), min_df=1)
    Xv  = vec.fit_transform(X)
    clf = LogisticRegression(max_iter=1000, multi_class="auto")
    clf.fit(Xv, y_id)

    (ART/"labels.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    joblib.dump(vec, ART/"vectorizer.joblib")
    joblib.dump(clf, ART/"model.joblib")
    return {"ok": True, "artifact_dir": str(ART), "labels": labels}

if __name__ == "__main__":
    import json as _j; print(_j.dumps(train(), ensure_ascii=False))
