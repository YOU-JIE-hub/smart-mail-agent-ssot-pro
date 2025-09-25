#!/usr/bin/env python3
import json, re, unicodedata, random, pickle
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.svm import LinearSVC

BASE = Path("data/intent/i_20250901_full.jsonl")
AUGS = [
  Path("data/intent/i_20250901_handcrafted_aug.jsonl"),
  Path("data/intent/i_20250901_complaint_boost.jsonl"),
]
SAFE_ANGLE = {"<EMAIL>","<PHONE>","<URL>","<ADDR>","<NAME>","<COMPANY>","<ORDER_ID>","<INVOICE_NO>","<AMOUNT>"}
LABELS = ["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]

OUTSPLIT = Path("data/intent_split_boost"); OUTSPLIT.mkdir(parents=True, exist_ok=True)
REPORTS  = Path("reports_boosted"); REPORTS.mkdir(parents=True, exist_ok=True)
ART      = Path("artifacts/intent_svm_plus_boost.pkl")

def load_jsonl(p):
    rows=[]
    with p.open("r",encoding="utf-8") as f:
        for i,ln in enumerate(f,1):
            if not ln.strip(): continue
            try: rows.append(json.loads(ln))
            except Exception as e: raise SystemExit(f"[FAIL] {p}:{i} 非 JSON：{e}")
    return rows

def norm_text(t):
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"^> .*?$","",t, flags=re.M)
    t = re.sub(r"\s+"," ",t).strip().lower()
    return t

def validate(rows, name):
    for i,r in enumerate(rows,1):
        for k in ("id","label","meta","text"):
            if k not in r: raise SystemExit(f"[FAIL] {name}:{i} 缺欄位 {k}")
        if r["label"] not in LABELS: raise SystemExit(f"[FAIL] {name}:{i} 非法標籤 {r['label']}")
        lang = r["meta"].get("language")
        if lang not in {"zh","en"}: raise SystemExit(f"[FAIL] {name}:{i} 語言不符 {lang}")
        t=r["text"]
        if not t.strip(): raise SystemExit(f"[FAIL] {name}:{i} text 空白")
        if re.search(r"https?://|www\.", t, re.I): raise SystemExit(f"[FAIL] {name}:{i} 含 URL")
        if re.search(r"\+?\d{1,3}[-\s]?\d{2,4}[-\s]?\d{3,4}[-\s]?\d{3,4}", t): raise SystemExit(f"[FAIL] {name}:{i} 含電話")
        for tok in re.findall(r"<[^>]+>", t):
            if tok not in SAFE_ANGLE: raise SystemExit(f"[FAIL] {name}:{i} 占位符不在白名單 {tok}")
    print(f"[OK] {name} 驗證通過：{len(rows)}")

base = load_jsonl(BASE)
aug = sum([load_jsonl(p) for p in AUGS], [])
validate(aug, "AUG_ALL")

# 去重 + 重新編 ID
seen=set((norm_text(r["text"]), r["label"]) for r in base)
aug_clean=[]
for r in aug:
    key=(norm_text(r["text"]), r["label"])
    if key in seen: continue
    seen.add(key); aug_clean.append(r)
for i,r in enumerate(aug_clean,1):
    r["id"]=f"a-20250901-{i:04d}"

rows = base + aug_clean
print("[DIST]", Counter(r["label"] for r in rows))
print("[LANG]", Counter(r["meta"]["language"] for r in rows))

# 固定舊 test （若存在）
TEST_OLD = Path("data/intent_split_hc/test.jsonl")
test_rows = load_jsonl(TEST_OLD) if TEST_OLD.exists() else []
test_keys = set((norm_text(r["text"]), r["label"]) for r in test_rows)
remain = [r for r in rows if (norm_text(r["text"]), r["label"]) not in test_keys]

# 分層切分 remain -> train/val（8:2）
X = list(range(len(remain))); y = [r["label"] for r in remain]
sss=StratifiedShuffleSplit(n_splits=1,test_size=0.2,random_state=42)
tr_idx, va_idx = next(sss.split(X,y))
train=[remain[i] for i in tr_idx]; val=[remain[i] for i in va_idx]
test = test_rows if test_rows else [rows[i] for i in va_idx[:15]]

def save_jsonl(items, p):
    with p.open("w",encoding="utf-8") as f:
        for r in items: f.write(json.dumps(r, ensure_ascii=False)+"\n")

save_jsonl(train, OUTSPLIT/"train.jsonl")
save_jsonl(val,   OUTSPLIT/"val.jsonl")
save_jsonl(test,  OUTSPLIT/"test.jsonl")
print(f"[SPLIT] train/val/test = {len(train)}/{len(val)}/{len(test)}")

# ====== 訓練 Keyword-boosted SVM ======
def make_regex_sources():
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
      r"\bfrustrated|concerns|inconsistent|delay|outage|no update|escalat(e|ion)|realistic ETA|unacceptable",
      r"簡介|先了解|評估中|Roadmap|案例|不是.*報價",
      r"\boverview|case studies|feasibility|gather(ing)? information|not .* pricing|intro deck",
      r"<AMOUNT>|NT\$|\bUSD\b", r"<INVOICE_NO>|發票|credit note|void",
      r"<ORDER_ID>", r"<EMAIL>|<PHONE>|<ADDR>|<COMPANY>|<NAME>",
      r"\bEOD\b|\bEOW\b|\bQ[1-4]\b|\d{1,2}:\d{2}|\d{1,2}/\d{1,2}", r"\bSLA\b|99\.\d{1,2}%"
    ]

def featurize_rx(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    mat=[[1 if rx.search(t) else 0 for rx in regs] for t in texts]
    return csr_matrix(np.array(mat, dtype=np.float32))

def oversample(X,y,seed=42):
    by=defaultdict(list)
    for i,lab in enumerate(y): by[lab].append(i)
    mx=max(len(ix) for ix in by.values())
    rng=random.Random(seed)
    Xo,yo=[],[]
    for lab,ix in by.items():
        take = ix + [rng.choice(ix) for _ in range(mx-len(ix))]
        for j in take: Xo.append(X[j]); yo.append(lab)
    return Xo,yo

Xtr=[r["text"] for r in train]; ytr=[r["label"] for r in train]
Xva=[r["text"] for r in val];   yva=[r["label"] for r in val]
Xte=[r["text"] for r in test];  yte=[r["label"] for r in test]

Xtr_bal, ytr_bal = oversample(Xtr, ytr)
char_vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))
word_vec = TfidfVectorizer(analyzer="word", ngram_range=(1,2), token_pattern=r"(?u)\b\w+\b")
rx_srcs  = make_regex_sources()

Xtr_all = hstack([char_vec.fit_transform(Xtr_bal), word_vec.fit_transform(Xtr_bal), featurize_rx(Xtr_bal, rx_srcs)])
Xva_all = hstack([char_vec.transform(Xva),         word_vec.transform(Xva),         featurize_rx(Xva, rx_srcs)])
Xte_all = hstack([char_vec.transform(Xte),         word_vec.transform(Xte),         featurize_rx(Xte, rx_srcs)])

best=(None,None,None)
for C in [0.5,1,2,4]:
    clf=LinearSVC(C=C, class_weight="balanced").fit(Xtr_all, ytr_bal)
    rep=classification_report(yva, clf.predict(Xva_all), labels=LABELS, output_dict=True, zero_division=0)
    f1=rep["macro avg"]["f1-score"]
    print(f"[VAL] C={C} macroF1={f1:.3f}")
    if not best[0] or f1>best[0]: best=(f1,C,clf)
f1,Cbest,clf = best
print(f"[PICK] C={Cbest} (VAL macroF1={f1:.3f})")

# Train+Val 重訓最終
Xtv = Xtr + Xva; ytv = ytr + yva
Xtv_bal, ytv_bal = oversample(Xtv, ytv)
Xtv_all = hstack([char_vec.fit_transform(Xtv_bal), word_vec.fit_transform(Xtv_bal), featurize_rx(Xtv_bal, rx_srcs)])
final = LinearSVC(C=Cbest, class_weight="balanced").fit(Xtv_all, ytv_bal)

# recompute test features with refitted vectorizers
Xte_all = hstack([char_vec.transform(Xte), word_vec.transform(Xte), featurize_rx(Xte, rx_srcs)])

# 保存 bundle
ART.parent.mkdir(parents=True, exist_ok=True)
with ART.open("wb") as f:
    pickle.dump({"labels":LABELS,"char_vec":char_vec,"word_vec":word_vec,"regex_sources":rx_srcs,"clf":final}, f)
print("[SAVED]", ART)

# 報告
rep_val = classification_report(yva, clf.predict(Xva_all), labels=LABELS, digits=3, zero_division=0)
rep_tst = classification_report(yte, final.predict(Xte_all), labels=LABELS, digits=3, zero_division=0)
(Path(REPORTS/"val_report.txt")).write_text(rep_val, encoding="utf-8")
(Path(REPORTS/"test_report.txt")).write_text(rep_tst, encoding="utf-8")
print("\n[VAL REPORT]\n"+rep_val)
print("\n[TEST REPORT]\n"+rep_tst)

cm = confusion_matrix(yte, final.predict(Xte_all), labels=LABELS)
lines=["\t"+"\t".join(LABELS)]
for i,row in enumerate(cm): lines.append(LABELS[i]+"\t"+"\t".join(map(str,row)))
(Path(REPORTS/"confusion_matrix.tsv")).write_text("\n".join(lines), encoding="utf-8")
print("[SAVED]", REPORTS/"confusion_matrix.tsv")
