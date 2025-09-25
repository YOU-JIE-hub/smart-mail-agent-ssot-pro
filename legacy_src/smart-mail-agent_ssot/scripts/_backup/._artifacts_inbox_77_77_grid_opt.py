import json,re,random,pickle
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.sparse import hstack,csr_matrix,vstack
from sklearn.model_selection import StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report,f1_score
from sklearn.svm import LinearSVC

random.seed(20250902); np.random.seed(20250902)
ROOT=Path(".")
FULL=ROOT/"data/intent/i_20250901_full.jsonl"
HC  =ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
CB  =ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
AUTO=ROOT/"data/intent/i_20250901_auto_aug.jsonl"
MERG=ROOT/"data/intent/i_20250901_merged.jsonl"
HOLD=ROOT/"data/intent/external_holdout.jsonl"
ART =ROOT/"artifacts/intent_svm_plus_auto.pkl"
REP =ROOT/"reports_auto/grid_cv.txt"
LABELS=["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]
PH={"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}

def R(p):
    a=[]; 
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln=ln.strip()
            if ln: a.append(json.loads(ln))
    return a

def okph(t):
    toks=set(re.findall(r"<([A-Z_]+)>",t))
    return toks.issubset(PH)

def norm_key(t):
    t=t.lower()
    t=re.sub(r"\s+","",t)
    t=re.sub(r"[^\w\u4e00-\u9fff<>]+","",t)
    return t

def rebuild_merged():
    seen=set(); out=[]
    for p in [FULL,HC,CB,AUTO,MERG]:
        if p.exists():
            for r in R(p):
                txt=r.get("text",""); lab=r.get("label"); lang=r.get("meta",{}).get("language")
                if not okph(txt): continue
                k=(lab,lang,norm_key(txt))
                if k in seen: continue
                seen.add(k); out.append(r)
    return out

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    mat=[[1 if rx.search(t) else 0 for rx in regs] for t in texts]
    return csr_matrix(np.array(mat, dtype=np.float32))

rx_srcs=[
    r"\bAPI\b", r"/v\d+/", r"\bUAT\b", r"\bprod(uction)?\b", r"sandbox", r"\b(429|500)\b",
    r"OTP|SSO|SAML|CORS|webhook|TLS|限流|驗簽|白名單",
    r"報價|詢價|SOW|折扣|總價|TCO|PoC|授權|年費|一次性|\bquote\b|\bpricing\b|USD|NT\$",
    r"退款|退費|提前終止|合約|條款|違約金|資料刪除|保留\s*90\s*天|升級|降級|\brefund|termination|policy|terms|credit note|void|retention|deletion|upgrade|downgrade",
    r"更新|變更|新增|刪除|白名單\s*IP|寄送地址|收件人|發票抬頭|\bupdate|billing email|recipient|whitelist",
    r"等太久|變慢|不一致|沒動靜|延宕|抱怨|\bslow|inconsistent|delay|outage|no update|escalat(e|ion)|ETA"
]

rows = rebuild_merged()
# 去掉 holdout：以 text 規範化去重
hold = R(HOLD)
hkeys=set((r.get("label"), r.get("meta",{}).get("language"), norm_key(r["text"])) for r in hold)
clean=[r for r in rows if (r["label"], r["meta"]["language"], norm_key(r["text"])) not in hkeys]

X=[r["text"] for r in clean]; y=[r["label"] for r in clean]
skf=StratifiedKFold(n_splits=5, shuffle=True, random_state=20250902)
Cs=[0.25,0.5,1.0,2.0,4.0]
log=[]
best=(None,-1.0)  # (C, macroF1)

for C in Cs:
    f1s=[]
    for tr,va in skf.split(X,y):
        Xtr=[X[i] for i in tr]; ytr=[y[i] for i in tr]
        Xva=[X[i] for i in va]; yva=[y[i] for i in va]
        char_vec=TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=1)
        word_vec=TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=1)
        Xc_tr=char_vec.fit_transform(Xtr); Xw_tr=word_vec.fit_transform(Xtr); Xr_tr=featurize_regex(Xtr, rx_srcs)
        Xc_va=char_vec.transform(Xva);   Xw_va=word_vec.transform(Xva);   Xr_va=featurize_regex(Xva, rx_srcs)
        Xt=hstack([Xc_tr,Xw_tr,Xr_tr]); Xv=hstack([Xc_va,Xw_va,Xr_va])

        # 簡單類別平衡（重抽樣）
        cnt=Counter(ytr); mx=max(cnt.values())
        parts=[]; yy=[]
        for lab in sorted(cnt):
            idx=[i for i,yy0 in enumerate(ytr) if yy0==lab]
            need=mx-len(idx)
            pick=idx + [random.choice(idx) for _ in range(need)]
            parts.append(hstack([char_vec.transform([Xtr[i] for i in pick]),
                                 word_vec.transform([Xtr[i] for i in pick]),
                                 featurize_regex([Xtr[i] for i in pick], rx_srcs)]))
            yy += [lab]*len(pick)
        Xt_bal=vstack(parts)

        clf=LinearSVC(C=C, class_weight="balanced").fit(Xt_bal, yy)
        pred=clf.predict(Xv)
        f1s.append(f1_score(yva, pred, labels=LABELS, average="macro", zero_division=0))
    mf=float(np.mean(f1s))
    log.append((C, mf))
    if mf>best[1]: best=(C,mf)

REP.parent.mkdir(parents=True, exist_ok=True)
with open(REP,"w",encoding="utf-8") as f:
    for C,mf in log: f.write(f"C={C}\tmacroF1={mf:.3f}\n")
    f.write(f"[PICK] C={best[0]} macroF1={best[1]:.3f}\n")

# 用最佳 C 在 clean 全量重訓（保留 vectorizer）
char_vec=TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=1)
word_vec=TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=1)
Xc=char_vec.fit_transform(X); Xw=word_vec.fit_transform(X); Xr=featurize_regex(X, rx_srcs)
Xt=hstack([Xc,Xw,Xr])
clf=LinearSVC(C=best[0], class_weight="balanced").fit(Xt, y)
with open(ART,"wb") as f:
    pickle.dump({"clf":clf,"char_vec":char_vec,"word_vec":word_vec,"regex_sources":rx_srcs}, f)
print("[GRID] saved", ART, "bestC", best[0])
