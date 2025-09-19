#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
train_pro.py
- 專業級意圖分類：字/詞 n-gram + 雙語法規/商務/技術詞庫 + 正則旗標
- 線性 SVM + CalibratedClassifierCV (sigmoid) 機率校準
- 產出：模型、報告(分類報告/混淆矩陣/錯誤TSV)、訓練卡
"""
import os, sys, json, re, argparse, random, time, math, hashlib
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils import shuffle

def read_jsonl(path: str) -> List[Dict[str, Any]]:
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
                data.append(obj)
            except Exception:
                # 退路：把整行當 text
                data.append({"text": line})
    return data

def join_subject_text(obj: Dict[str, Any]) -> str:
    # 常見欄位：subject, title, text, body；某些「clean」檔已把Subject拼進text
    parts = []
    for k in ("subject","Subject","title","Title"):
        if obj.get(k): parts.append(str(obj[k]))
    if obj.get("text"): parts.append(str(obj["text"]))
    elif obj.get("body"): parts.append(str(obj["body"]))
    s = "  ".join(parts).strip()
    return s if s else json.dumps(obj, ensure_ascii=False)

def detect_lang(s: str) -> str:
    # 粗略語言偵測：是否包含 CJK
    return "zh" if re.search(r"[\u4e00-\u9fff]", s) else "en"

# ====== 針對領域的雙語詞庫 ======
LEX = {
    "policy_qa": [
        # en
        "dpa","data processing addendum","gdpr","privacy","retention","audit log","cross-border",
        "cross border","notice period","auto-renewal","auto renewal","assignment","affiliate",
        "ico","security policy","sla","data deletion","backup",
        # zh
        "資料處理者附錄","跨境傳輸","隱私","保留","刪除","審計日誌","自動續約","到期通知",
        "契約","轉讓","關係企業","資安","合規","政策","條款","服務等級",
    ],
    "biz_quote": [
        "quote","pricing","discount","seat","users","annual","license","trial price",
        "報價","报价","折扣","年度授權","試算","方案","費用","NT$","USD","$",
    ],
    "tech_support": [
        "api","sdk","endpoint","status 500","500","error","bug","crash","log","trace","stack",
        "修復","錯誤","故障","日誌","連結","prod","環境","版本","部署","integration","timeout",
    ],
    "complaint": [
        "delay","postpone","slow","unstable","priority","escalate",
        "延期","變更","混亂","請改善","進度","不穩定","兩天","太慢","優先級","升級處理",
    ],
    "profile_update": [
        "change email","update email","billing","invoice","address","account",
        "更新資料","更改信箱","帳號","發票","統編","地址","抬頭","付款","信用卡",
    ],
    "other": [
        "overview","deck","case study","demo video","comparison",
        "概覽","簡報","成功案例","短介","比較","選型","架構圖","概要","先看",
    ],
}

RGX = {
    "has_amount": re.compile(r"(nt\$|\$|usd|eur|€|¥)\s*\d", re.I),
    "has_days": re.compile(r"(\b\d{1,3}\s*(day|week|month|days|weeks|months)\b|[0-9０-９]{1,3}\s*[天週月])", re.I),
    "has_trial": re.compile(r"\btrial|試用|延長試用", re.I),
    "has_contract": re.compile(r"contract|合約|自動續約|notice|到期通知|assignment|轉讓", re.I),
    "has_api_url": re.compile(r"<url>|https?://", re.I),
    "has_status_code": re.compile(r"\b[45]\d{2}\b"),
}

def lexicon_counts(s: str) -> Dict[str, int]:
    s_l = s.lower()
    out = {}
    for k, terms in LEX.items():
        c = 0
        for t in terms:
            if t.lower() in s_l: c += 1
        out[f"lex_{k}_hits"] = c
    return out

def regex_flags(s: str) -> Dict[str, int]:
    out = {}
    for k, rgx in RGX.items():
        out[k] = 1 if rgx.search(s) else 0
    out["lang_zh"] = 1 if detect_lang(s) == "zh" else 0
    return out

class DictFeaturizer:
    """將文字轉成 dict 特徵（詞庫計數 + 正則旗標）"""
    def fit(self, X, y=None): return self
    def transform(self, X):
        rows = []
        for s in X:
            d = {}
            d.update(lexicon_counts(s))
            d.update(regex_flags(s))
            rows.append(d)
        dv = DictVectorizer(sparse=True)
        mat = dv.fit_transform(rows)
        self.dv = dv
        return mat
    def fit_transform(self, X, y=None):
        self.dv = DictVectorizer(sparse=True)
        rows = []
        for s in X:
            d = {}
            d.update(lexicon_counts(s))
            d.update(regex_flags(s))
            rows.append(d)
        return self.dv.fit_transform(rows)

def build_pipeline(seed: int = 42):
    # 詞 + 字 n-gram；min_df 適中避免過擬合
    tf_word = TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=2, max_features=200000)
    tf_char = TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=3, max_features=400000)
    dict_feat = DictFeaturizer()

    feats = FeatureUnion([
        ("w", tf_word),
        ("c", tf_char),
        ("d", dict_feat),
    ])

    base = LinearSVC(C=1.0, class_weight="balanced", random_state=seed)
    clf = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3, n_jobs=None)
    return feats, clf

def ensure_dir(p):
    d = os.path.dirname(p)
    if d and not os.path.exists(d): os.makedirs(d, exist_ok=True)

def load_xy(train_path: str) -> Tuple[List[str], List[str]]:
    data = read_jsonl(train_path)
    X, y = [], []
    for r in data:
        txt = join_subject_text(r)
        lab = r.get("label") or r.get("gold") or r.get("intent") or r.get("y")
        if txt and lab:
            X.append(txt)
            y.append(lab)
    return X, y

def evaluate_and_write(y_true, y_pred, texts, ids, langs, prefix: str):
    ensure_dir(prefix)
    # 報告
    report_txt = classification_report(y_true, y_pred, digits=3)
    with open(prefix + "_eval_manual_pro.txt", "w", encoding="utf-8") as f:
        f.write(report_txt + "\n")
        # 混淆
        labels = sorted(list({*y_true, *y_pred}))
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        f.write("\n[CONFUSION]\n")
        f.write("\t" + "\t".join(labels) + "\n")
        for i, row in enumerate(cm):
            f.write(labels[i] + "\t" + "\t".join(str(x) for x in row) + "\n")

    # 分開存一份混淆（TSV）
    with open(prefix + "_confusion_pro.tsv", "w", encoding="utf-8") as f:
        labels = sorted(list({*y_true, *y_pred}))
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        f.write("label\t" + "\t".join(labels) + "\n")
        for i, row in enumerate(cm):
            f.write(labels[i] + "\t" + "\t".join(str(x) for x in row) + "\n")

    # 錯誤清單
    with open(prefix + "_errors_pro.tsv", "w", encoding="utf-8") as f:
        f.write("id\tlang\tgold\tpred\ttext\n")
        for i, (yt, yp) in enumerate(zip(y_true, y_pred)):
            if yt != yp:
                san = texts[i].replace("\t", " ").replace("\n", " ")
                f.write(f"{ids[i]}\t{langs[i]}\t{yt}\t{yp}\t{san}\n")




def parse_test(path: str) -> Tuple[List[str], List[str], List[str], List[str]]:
    data = read_jsonl(path)
    texts, labels, ids, langs = [], [], [], []
    for r in data:
        t = join_subject_text(r)
        y = r.get("label") or r.get("gold") or r.get("intent") or r.get("y")
        i = r.get("id") or r.get("mid") or f"row-{len(ids):04d}"
        lg = r.get("lang") or detect_lang(t)
        if t:
            texts.append(t)
            labels.append(y if y else "unknown")
            ids.append(i)
            langs.append(lg)
    return texts, labels, ids, langs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="data/intent/i_20250901_merged.jsonl")
    ap.add_argument("--test", default="data/intent/external_realistic_test.clean.jsonl")
    ap.add_argument("--model_out", default="artifacts/intent_pro_cal.pkl")
    ap.add_argument("--report_prefix", default="reports_auto/external")
    ap.add_argument("--seed", type=int, default=int(os.environ.get("SEED", 42)))
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed)

    print(f"[CFG] seed={args.seed}")
    print(f"[IN] train={args.train}")
    X, y = load_xy(args.train)
    print(f"[TRAIN] n={len(X)}  dist={Counter(y)}")

    feats, clf = build_pipeline(seed=args.seed)
    from sklearn.pipeline import Pipeline
    pipe = Pipeline([("feats", feats), ("clf", clf)])

    print("[FIT] training + calibration ...")
    pipe.fit(X, y)
    ensure_dir(args.model_out)
    import pickle, datetime
    meta = {
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "seed": args.seed,
        "train_path": args.train,
        "labels": sorted(list(set(y))),
        "notes": "pro pipeline: word/char ngrams + lexicon/regex features + calibrated LinearSVC",
    }
    with open(args.model_out, "wb") as f:
        pickle.dump({"model": pipe, "meta": meta}, f)
    print(f"[SAVED] {args.model_out}")

    # ==== 評估（如果 test 存在）====
    if args.test and os.path.isfile(args.test):
        Xt, Yt, IDs, LANGs = parse_test(args.test)
        print(f"[TEST] n={len(Xt)} (labels known={sum([1 for z in Yt if z!='unknown'])})")
        y_pred = pipe.predict(Xt)
        ensure_dir(args.report_prefix)
        evaluate_and_write(Yt, y_pred, Xt, IDs, LANGs, args.report_prefix)
        print("[REPORT] written -> "
              f"{args.report_prefix}_eval_manual_pro.txt, "
              f"{args.report_prefix}_confusion_pro.tsv, "
              f"{args.report_prefix}_errors_pro.tsv")
    else:
        print("[WARN] test file not found; skip evaluation")

    # 訓練卡
    card = [
        "# Model Card (intent_pro_cal)",
        f"- seed: {args.seed}",
        f"- train: {args.train}",
        f"- model_out: {args.model_out}",
        f"- features: word(1-2) tfidf, char(3-5) tfidf, lexicon & regex flags",
        "- classifier: LinearSVC (balanced) + sigmoid calibration (cv=3)",
    ]
    with open("reports_auto/model_card_pro.md", "w", encoding="utf-8") as f:
        f.write("\n".join(card))
    print("[CARD] reports_auto/model_card_pro.md")

if __name__ == "__main__":
    main()
