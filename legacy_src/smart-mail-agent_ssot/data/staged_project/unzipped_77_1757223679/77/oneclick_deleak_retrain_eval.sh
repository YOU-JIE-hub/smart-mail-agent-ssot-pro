#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
TEST="${1:-}"
[ -n "$TEST" ] || { echo "usage: $0 /abs/path/your_test.jsonl"; exit 2; }
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true
python - <<'PY'
import os,sys,re,json,random,datetime,pickle
from pathlib import Path
import numpy as np
from collections import Counter
from scipy.sparse import hstack,csr_matrix,vstack
from sklearn.metrics import classification_report,confusion_matrix
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

random.seed(20250901); np.random.seed(20250901)
ROOT=Path(".")
FULL=ROOT/"data/intent/i_20250901_full.jsonl"
HC  =ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
CB  =ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
# 安全起見：此流程不使用 AUTO 擴增資料，避免潛在語義洩漏
OUT_MERGED=ROOT/"data/intent/i_20250901_merged_clean.jsonl"
REMOVED=ROOT/"reports_auto/removed_due_to_test.tsv"
TS=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUTDIR=ROOT/f"reports_auto/clean_run_{TS}"
OUTDIR.mkdir(parents=True, exist_ok=True)
MODEL=ROOT/f"artifacts/intent_svm_plus_clean.pkl"

def read_jsonl(p):
    if not p.exists(): return []
    out=[]
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip(): out.append(json.loads(ln))
    return out

def write_jsonl(rows,p):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n",encoding="utf-8")

def norm_key(t):
    t=t.lower()
    t=re.sub(r"\s+","",t)
    t=re.sub(r"[^\w\u4e00-\u9fff<>]+","",t)
    return t

test_path=Path(os.environ.get("TEST_JSONL","")) or None
if not test_path:
    # 由 bash 傳遞
    test_path=Path(sys.argv[-1])
if not test_path.exists():
    print("[FAIL] test file missing:", test_path); sys.exit(3)

test_rows=read_jsonl(test_path)
test_set={norm_key(r["text"]) for r in test_rows}
print("[TEST_SZ]", len(test_rows))

srcs=[("full",FULL),("handcrafted",HC),("complaint_boost",CB)]
base=[]
for name,p in srcs:
    rows=read_jsonl(p)
    for r in rows:
        r["_src"]=name
    base+=rows
print("[SRC_SZ]", {n:len(read_jsonl(p)) for n,p in srcs})

seen=set(); merged=[]; removed=[]
for r in base:
    nk=norm_key(r["text"])
    if nk in seen: continue
    seen.add(nk)
    if nk in test_set:
        removed.append((r.get("id"), r.get("label"), r.get("meta",{}).get("language","?"), r["_src"], r["text"]))
    else:
        merged.append({k:v for k,v in r.items() if k!="_src"})

write_jsonl(merged, OUT_MERGED)
with open(REMOVED,"w",encoding="utf-8") as f:
    f.write("id\tlabel\tlang\tsource\ttext\n")
    for t in removed:
        f.write("\t".join(str(x) if x is not None else "" for x in t).replace("\n"," ")+"\n")

print("[LEAK_REMOVED]", len(removed))
print("[MERGED_CLEAN]", len(merged), OUT_MERGED)

LABELS=["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]
def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p,re.I) for p in rx_srcs]
    mat=[[1 if rx.search(t) else 0 for rx in regs] for t in texts]
    return csr_matrix(np.array(mat,dtype=np.float32))

rx_srcs=[
    r"\bAPI\b", r"/v\d+/", r"\bUAT\b", r"\bprod(uction)?\b", r"sandbox", r"\b(429|500)\b",
    r"OTP|SSO|SAML|CORS|webhook|TLS|限流|驗簽|白名單",
    r"報價|詢價|SOW|折扣|總價|TCO|PoC|授權|年費|一次性|試算|\bquote\b|\bpricing\b|USD|NT\$",
    r"退款|退費|提前終止|合約|條款|違約金|資料刪除|保留\s*90\s*天|升級|降級|\brefund|termination|policy|terms|credit note|void|retention|deletion|upgrade|downgrade",
    r"更新|變更|改為|新增|刪除|白名單\s*IP|寄送地址|收件人|發票抬頭|\bupdate|billing email|recipient|whitelist",
    r"等太久|困擾|太慢|不一致|沒動靜|延宕|抱怨|正面回應|\bfrustrated|concerns|inconsistent|delay|outage|no update|escalat(e|ion)|realistic ETA"
]

rows=read_jsonl(OUT_MERGED)
assert rows, "no clean training data"
X=[r["text"] for r in rows]; y=[r["label"] for r in rows]
sss=StratifiedShuffleSplit(n_splits=1, test_size=0.1, random_state=20250901)
idx_tr, idx_te = next(sss.split(X,y))
Xtr=[X[i] for i in idx_tr]; ytr=[y[i] for i in idx_tr]
Xte=[X[i] for i in idx_te]; yte=[y[i] for i in idx_te]
sss2=StratifiedShuffleSplit(n_splits=1, test_size=0.1111, random_state=20250901)
idx_tv, idx_va = next(sss2.split(Xtr,ytr))
Xtv=[Xtr[i] for i in idx_tv]; ytv=[ytr[i] for i in idx_tv]
Xva=[Xtr[i] for i in idx_va]; yva=[ytr[i] for i in idx_va]

char_vec=TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=1)
word_vec=TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=1)

Xc_tv=char_vec.fit_transform(Xtv); Xw_tv=word_vec.fit_transform(Xtv); Xr_tv=featurize_regex(Xtv, rx_srcs)
Xc_va=char_vec.transform(Xva);     Xw_va=word_vec.transform(Xva);     Xr_va=featurize_regex(Xva, rx_srcs)
Xc_te=char_vec.transform(Xte);     Xw_te=word_vec.transform(Xte);     Xr_te=featurize_regex(Xte, rx_srcs)

Xtv_all=hstack([Xc_tv,Xw_tv,Xr_tv]); Xva_all=hstack([Xc_va,Xw_va,Xr_va]); Xte_all=hstack([Xc_te,Xw_te,Xr_te])

# 簡單類別平衡（train-val）
cnt=Counter(ytv); mx=max(cnt.values()); parts=[]; ytv_bal=[]
for lab in sorted(cnt):
    idx=[i for i,yy in enumerate(ytv) if yy==lab]
    need=mx-len(idx)
    pick=idx + [random.choice(idx) for _ in range(need)]
    parts.append(hstack([char_vec.transform([Xtv[i] for i in pick]),
                         word_vec.transform([Xtv[i] for i in pick]),
                         featurize_regex([Xtv[i] for i in pick], rx_srcs)]))
    ytv_bal += [lab]*len(pick)
Xtv_bal=vstack(parts)

best=None; bestC=None
for C in [0.5,1,2,4]:
    clf=LinearSVC(C=C, class_weight="balanced").fit(Xtv_bal, ytv_bal)
    yp=clf.predict(Xva_all)
    rep=classification_report(yva, yp, labels=LABELS, digits=3, zero_division=0, output_dict=True)
    mf=rep["macro avg"]["f1-score"]
    if (best is None) or (mf>best): best=mf; bestC=C
# refit on train+val
Xc_tr=char_vec.fit_transform(Xtr); Xw_tr=word_vec.fit_transform(Xtr); Xr_tr=featurize_regex(Xtr, rx_srcs)
Xtr_all=hstack([Xc_tr,Xw_tr,Xr_tr])
final=LinearSVC(C=bestC, class_weight="balanced").fit(Xtr_all, ytr)

# 測報
def rep_txt(y_true, y_pred):
    return classification_report(y_true,y_pred,labels=LABELS,digits=3,zero_division=0)

Path("artifacts").mkdir(parents=True, exist_ok=True)
with open(MODEL,"wb") as f:
    pickle.dump({"clf":final,"char_vec":char_vec,"word_vec":word_vec,"regex_sources":rx_srcs}, f)
print("[SAVED]", MODEL)

# 內部 test
yp_te=final.predict(Xte_all)
(OUTDIR/"val_report.txt").write_text(rep_txt(yva, LinearSVC(C=bestC, class_weight="balanced").fit(Xtv_bal, ytv_bal).predict(Xva_all)), encoding="utf-8")
(OUTDIR/"test_report.txt").write_text(rep_txt(yte, yp_te), encoding="utf-8")
cm_te=confusion_matrix(yte, yp_te, labels=LABELS)
with (OUTDIR/"test_confusion.tsv").open("w",encoding="utf-8") as f:
    f.write("\t"+"\t".join(LABELS)+"\n")
    for i,row in enumerate(cm_te):
        f.write(LABELS[i]+"\t"+"\t".join(map(str,row))+"\n")

# 外部測試集
texts=[r["text"] for r in test_rows]
Xc=char_vec.transform(texts); Xw=word_vec.transform(texts); Xr=featurize_regex(texts, rx_srcs)
Xext=hstack([Xc,Xw,Xr])
y_have=all(("label" in r) for r in test_rows)
if y_have:
    yext=[r["label"] for r in test_rows]
    yhat=final.predict(Xext)
    rep=rep_txt(yext,yhat)
    (OUTDIR/"external_report.txt").write_text(rep,encoding="utf-8")
    cm=confusion_matrix(yext,yhat,labels=LABELS)
    with (OUTDIR/"external_confusion.tsv").open("w",encoding="utf-8") as f:
        f.write("\t"+"\t".join(LABELS)+"\n")
        for i,row in enumerate(cm):
            f.write(LABELS[i]+"\t"+"\t".join(map(str,row))+"\n")
    print("[EXT_EVAL] done ->", OUTDIR/"external_report.txt")
else:
    yhat=final.predict(Xext)
    with (OUTDIR/"external_preds.jsonl").open("w",encoding="utf-8") as f:
        for r,p in zip(test_rows,yhat):
            f.write(json.dumps({"id":r.get("id"),"text":r["text"],"pred":p},ensure_ascii=False)+"\n")
    print("[EXT_PRED] done ->", OUTDIR/"external_preds.jsonl")

print("[DONE]", str(OUTDIR))
PY
