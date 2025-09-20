import os, json, re, sys
from pathlib import Path
from datetime import datetime
from collections import Counter

import joblib
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import classification_report

ROOT = Path.cwd()
OUTDIR = ROOT / "reports_auto" / f"train_safe_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
OUTDIR.mkdir(parents=True, exist_ok=True)

def sniff_text_label(d):
    # 盡量容錯地找 text / label 欄位
    text = d.get("text") or d.get("body") or d.get("content") or d.get("message") or ""
    y = d.get("label") or d.get("target") or d.get("y")
    if isinstance(y, dict) and "label" in y:  # 兼容某些包法
        y = y["label"]
    # 標籤轉成 spam/ham 兩類
    if isinstance(y, (int, float)):
        y = "spam" if int(y) == 1 else "ham"
    elif isinstance(y, str):
        y = y.strip().lower()
        if y not in {"spam", "ham"}:
            # 隨便其他名字一律映為 ham（避免未知值），你也可以在這裡自定義 mapping
            y = "ham"
    else:
        y = "ham"
    return text, y

def read_jsonl(p: Path):
    rows = []
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            rows.append(sniff_text_label(d))
    X = [t for t,_ in rows]
    y = [c for _,c in rows]
    return X, y

def best_candidate():
    # 優先級：你剛掃到的兩個路徑
    cands = [
        Path("/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl"),
        Path("/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl"),
    ]
    # 也嘗試從 canuse 的 selection.json 抓
    canuse = sorted((ROOT/"reports_auto").glob("canuse_*/selection.json"))
    if canuse:
        try:
            j = json.loads(canuse[-1].read_text(encoding="utf-8"))
            for k in ("spam","intent"):
                if k in j and "path" in j[k]:
                    cands.insert(0, Path(j[k]["path"]))
        except Exception: pass
    # 回傳第一個存在的
    for c in cands:
        if c.exists(): return c
    raise SystemExit("找不到可用的 dataset.jsonl，請確認路徑")

def make_pipe():
    vec = TfidfVectorizer(
        ngram_range=(1,2),
        min_df=2,
        max_df=0.98,
        strip_accents="unicode",
        lowercase=True,
    )
    base = LinearSVC(C=1.0)
    # 先建個 dummy，實際 cv 會在下面調整
    clf = CalibratedClassifierCV(base_estimator=base, cv=3, method="sigmoid")
    return Pipeline([("tfidf", vec), ("clf", clf)])

def fit_safe(X, y):
    y = np.array(y)
    cnt = Counter(y)
    if len(cnt) < 2:
        raise SystemExit(f"資料只有單一類別：{cnt}")

    # 先切 train/valid（分層），避免 calib cv 遇到單類
    Xtr, Xva, ytr, yva = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    # 根據 ytr 的每類數量動態設定 n_splits
    min_class = min(Counter(ytr).values())
    n_splits = max(2, min(5, min_class))  # 至少2折，最多5折，不超過最小類別數
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    pipe = make_pipe()
    # 把 pipeline 內的 CalibratedClassifierCV 換成新的 skf
    pipe.set_params(clf__cv=skf)
    try:
        pipe.fit(Xtr, ytr)
    except ValueError as e:
        # 若仍因某折單類出錯，就退而求其次：先訓練 base，再用 'prefit' 單一驗證集做校正
        if "needs samples of at least 2 classes" in str(e):
            vec = pipe.named_steps["tfidf"]
            base = LinearSVC(C=1.0)
            Xtr_vec = vec.fit_transform(Xtr)
            base.fit(Xtr_vec, ytr)
            # calib with prefit
            cal = CalibratedClassifierCV(base_estimator=base, method="sigmoid", cv="prefit")
            cal.fit(vec.transform(Xva), yva)
            from sklearn.pipeline import make_pipeline
            pipe = make_pipeline(vec, cal)
        else:
            raise

    # 報表
    yhat = pipe.predict(Xva)
    rep = classification_report(yva, yhat, output_dict=True)
    return pipe, rep

def main():
    ds = best_candidate()
    print(f"[use] dataset: {ds}")
    X, y = read_jsonl(ds)
    print(f"[stats] n={len(y)} labels={Counter(y)}")
    model, rep = fit_safe(X, y)

    # 存成果（同時丟 intent/spam 兩個目錄一份，方便現有程式掛載）
    for sub in ("intent","spam"):
        outp = ROOT/"models"/sub/"artifacts"/"model_pipeline.pkl"
        outp.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, outp)
    # 報表 & 環境檔
    (OUTDIR/"report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), "utf-8")
    (OUTDIR/"MODEL_PATHS.auto.env").write_text(
        f"INTENT_PKL={ROOT}/models/intent/artifacts/model_pipeline.pkl\n"
        f"SPAM_PKL={ROOT}/models/spam/artifacts/model_pipeline.pkl\n", "utf-8"
    )
    print("\n=== OUTPUTS ===")
    print("intent pkl :", ROOT/"models/intent/artifacts/model_pipeline.pkl")
    print("spam   pkl :", ROOT/"models/spam/artifacts/model_pipeline.pkl")
    print("report    :", OUTDIR/"report.json")
    print("env       :", OUTDIR/"MODEL_PATHS.auto.env")

if __name__ == "__main__":
    main()
