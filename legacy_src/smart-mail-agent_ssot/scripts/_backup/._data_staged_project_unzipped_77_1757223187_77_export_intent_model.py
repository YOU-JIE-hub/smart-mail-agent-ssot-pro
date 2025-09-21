#!/usr/bin/env python3
from __future__ import annotations
import json, re, pickle, random
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report
from sklearn.svm import LinearSVC

LABELS = ["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]
SPLIT  = Path("data/intent_split_hc")
ART    = Path("artifacts/intent_svm_plus.pkl")

def load_xy(p: Path):
    X,y=[],[]
    with p.open("r",encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                o=json.loads(ln); X.append(o["text"]); y.append(o["label"])
    return X,y

def get_regex_sources():
    return [
      r"\bAPI\b", r"/v\d+/", r"\bUAT\b", r"\bprod(uction)?\b", r"sandbox", r"\b(429|500)\b",
      r"TLS|憑證|SAML|SSO|OTP|webhook|CORS|限流|錯誤|失敗|上傳|驗簽|白名單",
      r"報價|詢價|SOW|折扣|總價|TCO|PoC|授權|年費|一次性|試算",
      r"\bquote|pricing|SOW|discount|TCO|PoC|seats?\b|annual|total|USD|NT\$",
      r"退費|退款|提前終止|合約|條款|違約金|資料刪除|保留\s*90\s*天|升級|降級|發票.*(作廢|折讓)",
      r"\brefund|termination|policy|terms|penalt(y|ies)|credit note|void|retention|deletion|upgrade|downgrade",
      r"更新|變更|改為|新增|刪除|白名單\s*IP|寄送地址|收件人|發票抬頭",
      r"\bupdate|change|modify|billing email|address|recipient|whitelist",
      r"等太久|困擾|太慢|不一致|沒動靜|延宕|抱怨|請正面|重視|影響|延遲",
      r"\boverview|case studies|feasibility|gather(ing)? information|not .* pricing|intro deck",
      r"<AMOUNT>|NT\$|\bUSD\b", r"<INVOICE_NO>|發票|credit note|void",
      r"<ORDER_ID>", r"<EMAIL>|<PHONE>|<ADDR>|<COMPANY>|<NAME>",
      r"\bEOD\b|\bEOW\b|\bQ[1-4]\b|\d{1,2}:\d{2}|\d{1,2}/\d{1,2}", r"\bSLA\b|99\.\d{1,2}%"
    ]

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    mat = [[1 if rx.search(t) else 0 for rx in regs] for t in texts]
    return csr_matrix(np.array(mat, dtype=np.float32))

def oversample(X, y, seed=42):
    by=defaultdict(list)
    for i,lab in enumerate(y): by[lab].append(i)
    mx=max(len(ix) for ix in by.values())
    rng=random.Random(seed)
    Xo, yo = [], []
    for lab, ix in by.items():
        take = ix + [rng.choice(ix) for _ in range(mx-len(ix))]
        for j in take: Xo.append(X[j]); yo.append(lab)
    return Xo, yo

# 讀 split
if not (SPLIT/"train.jsonl").exists():
    print("[SKIP] data/intent_split_hc 不存在，略過 export。"); raise SystemExit(0)

Xtr,ytr = load_xy(SPLIT/"train.jsonl")
Xva,yva = load_xy(SPLIT/"val.jsonl")
Xte,yte = load_xy(SPLIT/"test.jsonl")
print("[Split] train/val/test =", len(Xtr), len(Xva), len(Xte))

char_vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))
word_vec = TfidfVectorizer(analyzer="word",   ngram_range=(1,2), token_pattern=r"(?u)\b\w+\b")
rx_srcs  = get_regex_sources()

# 過採樣
Xtr_bal, ytr_bal = oversample(Xtr, ytr)
from scipy.sparse import hstack
Xtr_all = hstack([char_vec.fit_transform(Xtr_bal),
                  word_vec.fit_transform(Xtr_bal),
                  featurize_regex(Xtr_bal, rx_srcs)])
Xva_all = hstack([char_vec.transform(Xva),
                  word_vec.transform(Xva),
                  featurize_regex(Xva, rx_srcs)])
best=(None,None,None)
for C in [0.5,1,2,4]:
    clf=LinearSVC(C=C, class_weight="balanced").fit(Xtr_all, ytr_bal)
    rep=classification_report(yva, clf.predict(Xva_all), labels=LABELS, output_dict=True, zero_division=0)
    f1=rep["macro avg"]["f1-score"]
    print(f"[VAL] C={C} macroF1={f1:.3f}")
    if not best[0] or f1>best[0]: best=(f1,C,clf)
f1,Cbest,_=best
print(f"[PICK] C={Cbest} (VAL macroF1={f1:.3f})")

# train+val 重訓
Xtv = Xtr+Xva; ytv = ytr+yva
Xtv_bal, ytv_bal = oversample(Xtv, ytv)
Xtv_all = hstack([char_vec.fit_transform(Xtv_bal),
                  word_vec.fit_transform(Xtv_bal),
                  featurize_regex(Xtv_bal, rx_srcs)])
final = LinearSVC(C=Cbest, class_weight="balanced").fit(Xtv_all, ytv_bal)

ART.parent.mkdir(parents=True, exist_ok=True)
with ART.open("wb") as f:
    pickle.dump({"labels":LABELS,"char_vec":char_vec,"word_vec":word_vec,"regex_sources":rx_srcs,"clf":final}, f)
print("[SAVED]", ART)

# 參考測試分數
ytp = final.predict(hstack([char_vec.transform(Xte),
                            word_vec.transform(Xte),
                            featurize_regex(Xte, rx_srcs)]))
print("\n[TEST REPORT]\n"+classification_report(yte, ytp, labels=LABELS, digits=3, zero_division=0))
