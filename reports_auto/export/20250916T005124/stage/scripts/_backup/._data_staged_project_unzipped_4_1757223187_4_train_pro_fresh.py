#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, pickle
from pathlib import Path
from collections import Counter

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import FunctionTransformer
from sklearn.pipeline import Pipeline, FeatureUnion
from rules_features import rules_feat
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold

# --- 輕量規則特徵（補 policy_qa / other 的語意訊號）---
API_TERMS    = ["api","sdk","rest","swagger","endpoint","token","webhook","api 文件","整合"]
POLICY_TERMS = ["dpa","data processing","cross-border","renew","expiry","assignment","處理者附錄","跨境","到期","續約","刪除","資料保存"]
ERROR_TERMS  = ["error","fail","cannot","timeout","429","5xx","saml","ntp","錯誤","失敗","無法","逾時","502","503","504"]
PRICE_TERMS  = ["quote","price","pricing","tco","sow","報價","總價","折扣","年費","專案價"]
PROFILE_TERMS= ["contact","sms","phone","更新聯絡人","更新電話","update contact","alert list"]

def rules_feat(texts):
    rows=[]
    for t in texts:
        z=(t or "").lower()
        f_api    = int(any(w in z for w in API_TERMS))
        f_policy = int(any(w in z for w in POLICY_TERMS))
        f_error  = int(any(w in z for w in ERROR_TERMS))
        f_price  = int(any(w in z for w in PRICE_TERMS))
        f_prof   = int(any(w in z for w in PROFILE_TERMS))
        f_digit  = int(any(c.isdigit() for c in z))
        f_url    = int(("http" in z) or ("www." in z))
        rows.append([f_api,f_policy,f_error,f_price,f_prof,f_digit,f_url])
    A = np.asarray(rows, dtype="float64")
    return sparse.csr_matrix(A)

def read_jsonl_text_label(p: Path):
    X,Y=[],[]
    with open(p,"r",encoding="utf-8") as f:
        for ln in f:
            o=json.loads(ln)
            y=o.get("label") or o.get("intent") or o.get("y")
            t=o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
            if y and t:
                X.append((t or "").strip()); Y.append(y)
    return X,Y

def macro_f1(y_true, y_pred, labels):
    out=[]
    for lab in labels:
        tp=fp=fn=0
        for yt,yp in zip(y_true,y_pred):
            tp += (yt==lab and yp==lab)
            fp += (yt!=lab and yp==lab)
            fn += (yt==lab and yp!=lab)
        P = tp/(tp+fp) if (tp+fp)>0 else 0.0
        R = tp/(tp+fn) if (tp+fn)>0 else 0.0
        F = (2*P*R/(P+R)) if (P+R)>0 else 0.0
        out.append(F)
    return float(np.mean(out)) if out else 0.0

def build_feats(max_df=1.0):
    word = TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=1, max_df=max_df)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=1, max_df=max_df)
    rules = FunctionTransformer(rules_feat, accept_sparse=True, validate=False)
    return FeatureUnion([("word",word),("char",char),("rules",rules)])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--out_model", required=True)
    ap.add_argument("--out_prefix", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--Cs", default="0.5,1.0,2.0")
    ap.add_argument("--max_df", type=float, default=1.0)
    args = ap.parse_args()

    Xtr, Ytr = read_jsonl_text_label(Path(args.train))
    Xte, Yte = read_jsonl_text_label(Path(args.test))
    labels = sorted(list(set(Ytr) | set(Yte)))
    print(f"[TRAIN] n={len(Xtr)} dist={Counter(Ytr)}")
    print(f"[TEST ] n={len(Xte)}")

    Cs = [float(x) for x in args.Cs.split(",")]
    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=args.seed)
    best = None

    for C in Cs:
        f1s=[]
        for tr_idx, va_idx in skf.split(Xtr, Ytr):
            X_tr = [Xtr[i] for i in tr_idx]; y_tr=[Ytr[i] for i in tr_idx]
            X_va = [Xtr[i] for i in va_idx]; y_va=[Ytr[i] for i in va_idx]
            feats = build_feats(max_df=args.max_df)
            base  = LinearSVC(C=C, class_weight="balanced", random_state=args.seed)
            clf   = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
            pipe  = Pipeline([("features",feats),("clf",clf)])
            pipe.fit(X_tr, y_tr)
            y_hat = pipe.predict(X_va)
            f1s.append(macro_f1(y_va, y_hat, labels))
        avg = float(np.mean(f1s))
        print(f"[CV] C={C} macroF1={avg:.4f}")
        if best is None or avg>best[0]:
            best=(avg,C)

    bestF1, bestC = best
    print(f"[BEST] C={bestC} (cv-macroF1={bestF1:.4f})")

    feats = build_feats(max_df=args.max_df)
    base  = LinearSVC(C=bestC, class_weight="balanced", random_state=args.seed)
    clf   = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    pipe  = Pipeline([("features",feats),("clf",clf)])
    pipe.fit(Xtr, Ytr)

    out = Path(args.out_model); out.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump({"pipeline": pipe}, open(out,"wb"))
    print("[SAVED]", out.resolve())

    # 測試評分 + 混淆 + 錯誤清單
    y_pred = pipe.predict(Xte)
    acc = sum(yt==yp for yt,yp in zip(Yte,y_pred))/len(Yte)
    mac = macro_f1(Yte, y_pred, labels)
    p_eval = Path(args.out_prefix + "_eval.txt")
    p_conf = Path(args.out_prefix + "_confusion.tsv")
    p_errs = Path(args.out_prefix + "_errors.tsv")

    # confusion
    idx={lab:i for i,lab in enumerate(labels)}
    M=np.zeros((len(labels),len(labels)),dtype=int)
    for a,b in zip(Yte,y_pred):
        if a in idx and b in idx: M[idx[a],idx[b]]+=1

    with open(p_eval,"w",encoding="utf-8") as fo:
        fo.write(f"pairs={len(Yte)}\nAccuracy={acc:.4f}\nMacroF1={mac:.4f}\n")
        for lab in labels:
            tp=fp=fn=0
            for yt,yp in zip(Yte,y_pred):
                tp += (yt==lab and yp==lab)
                fp += (yt!=lab and yp==lab)
                fn += (yt==lab and yp!=lab)
            P = tp/(tp+fp) if (tp+fp)>0 else 0.0
            R = tp/(tp+fn) if (tp+fn)>0 else 0.0
            F = (2*P*R/(P+R)) if (P+R)>0 else 0.0
            fo.write(f"{lab}: P={P:.4f} R={R:.4f} F1={F:.4f} (tp={tp},fp={fp},fn={fn})\n")

    with open(p_conf,"w",encoding="utf-8") as fo:
        fo.write("label\t"+"\t".join(labels)+"\n")
        for i,lab in enumerate(labels):
            fo.write(lab+"\t"+"\t".join(str(int(x)) for x in M[i])+"\n")

    with open(p_errs,"w",encoding="utf-8") as fo:
        fo.write("id\tlang\tgold\tpred\ttext\n")
        for (txt,yt),yp in zip(zip(Xte,Yte), y_pred):
            if yt!=yp:
                san=(txt or "").replace("\t"," ").replace("\n"," ")
                fo.write(f"\t\t{yt}\t{yp}\t{san[:500]}\n")

    print("[OUT]", p_eval, p_conf, p_errs)

if __name__ == "__main__":
    main()
