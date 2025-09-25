#!/usr/bin/env python3
import json,re,random,pickle
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.sparse import hstack,csr_matrix,vstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report,confusion_matrix
from sklearn.svm import LinearSVC
random.seed(20250901); np.random.seed(20250901)

ROOT=Path(".")
TRN=ROOT/"data/intent_split/train.jsonl"
VAL=ROOT/"data/intent_split/val.jsonl"
TST=ROOT/"data/intent_split/test.jsonl"
REP=ROOT/"reports_split"
ART=ROOT/"artifacts/intent_svm_plus_split.pkl"
LABELS=["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]
PH={"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}

def R(p):
    a=[]; 
    with p.open("r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if ln: a.append(json.loads(ln))
    return a

def okph(t):
    toks=set(re.findall(r"<([A-Z_]+)>",t))
    return toks.issubset(PH)

def key(t):
    t=t.lower(); t=re.sub(r"\s+","",t); t=re.sub(r"[^\w\u4e00-\u9fff<>]+","",t); return t

def rx(texts, srcs):
    regs=[re.compile(p,re.I) for p in srcs]
    return np.array([[1 if r.search(x) else 0 for r in regs] for x in texts], dtype=np.float32)

RX=[
 r"\bAPI\b", r"/v\d+/", r"\bUAT\b", r"\bprod(uction)?\b", r"sandbox", r"\b(429|500)\b",
 r"OTP|SSO|SAML|CORS|webhook|TLS|限流|驗簽|白名單",
 r"報價|詢價|SOW|折扣|總價|TCO|PoC|授權|年費|一次性|試算|\bquote\b|\bpricing\b|USD|NT\$",
 r"退款|退費|提前終止|合約|條款|違約金|資料刪除|保留\s*90\s*天|升級|降級|\brefund|termination|policy|terms|credit note|void|retention|deletion|upgrade|downgrade",
 r"更新|變更|改為|新增|刪除|白名單\s*IP|寄送地址|收件人|發票抬頭|\bupdate|billing email|recipient|whitelist",
 r"等太久|困擾|太慢|不一致|沒動靜|延宕|抱怨|\bfrustrated|concerns|inconsistent|delay|outage|no update|escalat(e|ion)|realistic ETA"
]

def clean(rows):
    out=[]; seen=set()
    for r in rows:
        t=r.get("text",""); 
        if not okph(t): continue
        k=(r.get("label"), r.get("meta",{}).get("language"), key(t))
        if k in seen: continue
        seen.add(k); out.append(r)
    return out

def main():
    assert TRN.exists() and VAL.exists() and TST.exists(), "missing data/intent_split/{train,val,test}.jsonl"
    train=clean(R(TRN)); val=clean(R(VAL)); test=clean(R(TST))
    kv={key(r["text"]) for r in val}; kt={key(r["text"]) for r in test}
    train=[r for r in train if key(r["text"]) not in kv|kt]

    Xtr=[r["text"] for r in train]; ytr=[r["label"] for r in train]
    Xva=[r["text"] for r in val];   yva=[r["label"] for r in val]
    Xte=[r["text"] for r in test];  yte=[r["label"] for r in test]

    char=TfidfVectorizer(analyzer="char_wb",ngram_range=(3,5),min_df=1)
    word=TfidfVectorizer(analyzer="word",ngram_range=(1,2),min_df=1)

    Xc_tr=char.fit_transform(Xtr); Xw_tr=word.fit_transform(Xtr); Xr_tr=csr_matrix(rx(Xtr,RX))
    Xc_va=char.transform(Xva);     Xw_va=word.transform(Xva);     Xr_va=csr_matrix(rx(Xva,RX))
    Xtr_all=hstack([Xc_tr,Xw_tr,Xr_tr]); Xva_all=hstack([Xc_va,Xw_va,Xr_va])

    from collections import Counter
    cnt=Counter(ytr); mx=max(cnt.values()); from scipy.sparse import vstack
    Xb=[]; yb=[]
    for lab in sorted(cnt):
        idx=[i for i,y in enumerate(ytr) if y==lab]; need=mx-len(idx)
        pick=idx + [random.choice(idx) for _ in range(need)]
        Xb.append(hstack([char.transform([Xtr[i] for i in pick]),
                          word.transform([Xtr[i] for i in pick]),
                          csr_matrix(rx([Xtr[i] for i in pick],RX))]))
        yb += [lab]*len(pick)
    Xb=vstack(Xb)

    best=None; bestC=None
    for C in [0.5,1,2,4]:
        clf=LinearSVC(C=C,class_weight="balanced").fit(Xb,yb)
        rep=classification_report(yva, clf.predict(Xva_all), labels=LABELS, digits=3, zero_division=0, output_dict=True)
        mf=rep["macro avg"]["f1-score"]
        if (best is None) or (mf>best): best=mf; bestC=C

    Xtv = Xtr + Xva; ytv = ytr + yva
    Xc_tv=char.fit_transform(Xtv); Xw_tv=word.fit_transform(Xtv); Xr_tv=csr_matrix(rx(Xtv,RX))
    Xtv_all=hstack([Xc_tv,Xw_tv,Xr_tv])
    final=LinearSVC(C=bestC,class_weight="balanced").fit(Xtv_all,ytv)

    Xc_te=char.transform(Xte); Xw_te=word.transform(Xte); Xr_te=csr_matrix(rx(Xte,RX))
    Xte_all=hstack([Xc_te,Xw_te,Xr_te])

    ART.parent.mkdir(parents=True,exist_ok=True)
    with open(ART,"wb") as f:
        pickle.dump({"clf":final,"char_vec":char,"word_vec":word,"regex_sources":RX}, f)
    print("[SAVED]", ART)

    REP.mkdir(parents=True,exist_ok=True)
    rep_va=classification_report(yva, LinearSVC(C=bestC,class_weight="balanced").fit(Xb,yb).predict(Xva_all), labels=LABELS, digits=3, zero_division=0)
    rep_te=classification_report(yte, final.predict(Xte_all), labels=LABELS, digits=3, zero_division=0)
    (REP/"val_report.txt").write_text(rep_va,encoding="utf-8")
    (REP/"test_report.txt").write_text(rep_te,encoding="utf-8")
    cm=confusion_matrix(yte, final.predict(Xte_all), labels=LABELS)
    with (REP/"confusion_matrix.tsv").open("w",encoding="utf-8") as f:
        f.write("\t"+"\t".join(LABELS)+"\n")
        for i,row in enumerate(cm):
            f.write(LABELS[i]+"\t"+"\t".join(map(str,row))+"\n")
    print("[VAL]\n"+rep_va+"\n[TEST]\n"+rep_te)
    print("[DONE] reports_split/{val_report.txt,test_report.txt,confusion_matrix.tsv}")
if __name__=="__main__": main()
