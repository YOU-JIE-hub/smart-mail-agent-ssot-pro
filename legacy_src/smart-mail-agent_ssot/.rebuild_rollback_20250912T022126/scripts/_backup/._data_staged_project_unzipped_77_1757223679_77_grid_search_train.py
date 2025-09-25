#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import random, json, re, numpy as np, pickle
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report
from scipy.sparse import csr_matrix, hstack, vstack
random.seed(20250901); np.random.seed(20250901)
ROOT=Path(".")
FULL=ROOT/"data/intent/i_20250901_full.jsonl"
HC=ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
CB=ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
AUTO=ROOT/"data/intent/i_20250901_auto_aug.jsonl"
MERG=ROOT/"data/intent/i_20250901_merged.jsonl"
REP=ROOT/"reports_auto"; REP.mkdir(parents=True, exist_ok=True)
ART=ROOT/"artifacts"; ART.mkdir(parents=True, exist_ok=True)
LABELS=["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]
def read_jsonl(p):
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
def okph(t):
    toks=set(re.findall(r"<([A-Z_]+)>",t))
    allow={"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}
    return toks.issubset(allow)
def rebuild():
    seen=set(); out=[]
    for p in [FULL,HC,CB,AUTO,MERG]:
        if p.exists():
            for ln in p.read_text(encoding="utf-8").splitlines():
                if not ln.strip(): continue
                r=json.loads(ln)
                t=r.get("text",""); lab=r.get("label")
                if not t or not lab or not okph(t): continue
                k=(lab, r.get("meta",{}).get("language"), t.lower())
                if k in seen: continue
                seen.add(k); out.append(r)
    return out
rows = read_jsonl(MERG) or rebuild()
assert rows, "no data"
X=[r["text"] for r in rows]; y=[r["label"] for r in rows]
sss=StratifiedShuffleSplit(n_splits=1, test_size=0.1, random_state=20250901)
idx_tr, idx_te = next(sss.split(X,y))
Xtr=[X[i] for i in idx_tr]; ytr=[y[i] for i in idx_tr]
Xte=[X[i] for i in idx_te]; yte=[y[i] for i in idx_te]
sss2=StratifiedShuffleSplit(n_splits=1, test_size=0.1111, random_state=20250901)
idx_tv, idx_va = next(sss2.split(Xtr,ytr))
Xtv=[Xtr[i] for i in idx_tv]; ytv=[ytr[i] for i in idx_tv]
Xva=[Xtr[i] for i in idx_va]; yva=[ytr[i] for i in idx_va]
rx_srcs=[
    r"\bAPI\b", r"/v\d+/", r"\bUAT\b", r"\bprod(uction)?\b", r"sandbox", r"\b(429|500)\b",
    r"OTP|SSO|SAML|CORS|webhook|TLS|限流|驗簽|白名單",
    r"報價|詢價|SOW|折扣|總價|TCO|PoC|授權|年費|一次性|試算|\bquote\b|\bpricing\b|USD|NT\$",
    r"退款|退費|提前終止|合約|條款|違約金|資料刪除|保留\s*90\s*天|升級|降級|\brefund|termination|policy|terms|credit note|void|retention|deletion|upgrade|downgrade",
    r"更新|變更|改為|新增|刪除|白名單\s*IP|寄送地址|收件人|發票抬頭|\bupdate|billing email|recipient|whitelist",
    r"等太久|困擾|太慢|不一致|沒動靜|延宕|抱怨|正面回應|\bfrustrated|concerns|inconsistent|delay|outage|no update|escalat(e|ion)|realistic ETA"
]
def rx_feat(texts):
    regs=[re.compile(p,re.I) for p in rx_srcs]
    return csr_matrix(np.array([[1 if r.search(t) else 0 for r in regs] for t in texts], dtype=np.float32))
def oversample(Xs, ys):
    cnt=Counter(ys); mx=max(cnt.values())
    buckets=[]
    for lab in sorted(cnt):
        idx=[i for i,yy in enumerate(ys) if yy==lab]
        pick=idx + [random.choice(idx) for _ in range(mx-len(idx))]
        buckets.append(hstack([Xs[0][pick[0]:pick[0]+1].__class__.vstack([Xs[0][i] for i in pick]),
                               Xs[1][pick[0]:pick[0]+1].__class__.vstack([Xs[1][i] for i in pick]),
                               Xs[2][pick[0]:pick[0]+1].__class__.vstack([Xs[2][i] for i in pick])]))
    return vstack(buckets), sum(([lab]*mx for lab in sorted(cnt)), [])
def eval_conf(char_range, word_range, min_df, C):
    ch=TfidfVectorizer(analyzer="char_wb", ngram_range=char_range, min_df=min_df)
    wd=TfidfVectorizer(analyzer="word", ngram_range=word_range, min_df=min_df)
    Xc=ch.fit_transform(Xtv); Xw=wd.fit_transform(Xtv); Xr=rx_feat(Xtv)
    Xva_all=hstack([ch.transform(Xva), wd.transform(Xva), rx_feat(Xva)])
    # oversample on train-val
    # 為了簡潔，這裡用不平衡直接訓練（LinearSVC + balanced），速度更快
    clf=LinearSVC(C=C, class_weight="balanced").fit(hstack([Xc,Xw,Xr]), ytv)
    yp=clf.predict(Xva_all)
    rep=classification_report(yva, yp, labels=LABELS, digits=3, zero_division=0, output_dict=True)
    mf=rep["macro avg"]["f1-score"]
    return mf, ch, wd, clf
grid=[]
for char_range in [(3,5),(2,5)]:
    for word_range in [(1,2),(1,3)]:
        for min_df in [1,2]:
            for C in [0.5,1,2,4]:
                mf, ch, wd, clf = eval_conf(char_range, word_range, min_df, C)
                grid.append((mf, char_range, word_range, min_df, C, ch, wd, clf))
grid.sort(key=lambda x: x[0], reverse=True)
best=grid[0]; mf, char_range, word_range, min_df, C, ch, wd, clf = best
# retrain on (train+val)
ch = TfidfVectorizer(analyzer="char_wb", ngram_range=char_range, min_df=min_df).fit(Xtr)
wd = TfidfVectorizer(analyzer="word",    ngram_range=word_range, min_df=min_df).fit(Xtr)
Xtr_all=hstack([ch.transform(Xtr), wd.transform(Xtr), rx_feat(Xtr)])
final=LinearSVC(C=C, class_weight="balanced").fit(Xtr_all, ytr)
# save
with open(ART/"intent_svm_plus_best.pkl","wb") as f:
    pickle.dump({"clf":final,"char_vec":ch,"word_vec":wd,"regex_sources":rx_srcs}, f)
# report
with open(REP/"opt_grid.tsv","w",encoding="utf-8") as f:
    f.write("macroF1\tchar\tword\tmin_df\tC\n")
    for rec in grid[:20]:
        f.write(f"{rec[0]:.3f}\t{rec[1]}\t{rec[2]}\t{rec[3]}\t{rec[4]}\n")
with open(REP/"opt_best.txt","w",encoding="utf-8") as f:
    f.write(f"best macroF1={mf:.3f}, char={char_range}, word={word_range}, min_df={min_df}, C={C}\n")
print(f"[BEST] macroF1={mf:.3f} char={char_range} word={word_range} min_df={min_df} C={C}")
