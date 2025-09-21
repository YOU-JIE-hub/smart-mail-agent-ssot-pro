import json, re, random
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.sparse import hstack, csr_matrix, vstack
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.svm import LinearSVC
random.seed(20250901); np.random.seed(20250901)
ROOT=Path("."); FULL=ROOT/"data/intent/i_20250901_full.jsonl"; HC=ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"; CB=ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
AUTO=ROOT/"data/intent/i_20250901_auto_aug.jsonl"; MERG=ROOT/"data/intent/i_20250901_merged.jsonl"; SPLT=ROOT/"data/intent_split_auto"; REP=ROOT/"reports_auto"; ART=ROOT/"artifacts/intent_svm_plus_auto.pkl"
LABELS=["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]; PH={"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}
def R(p): 
    a=[]
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln=ln.strip()
            if ln: a.append(json.loads(ln))
    return a
def W(rows,p): p.parent.mkdir(parents=True,exist_ok=True); p.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n",encoding="utf-8")
def okph(t): 
    import re
    toks=set(re.findall(r"<([A-Z_]+)>",t)); return toks.issubset(PH)
def normk(t):
    import re
    t=t.lower(); t=re.sub(r"\s+","",t); return re.sub(r"[^\w\u4e00-\u9fff<>]+","",t)
def maybe(p): import random; return random.random()<p
def swap(t,pairs):
    import re,random
    for pat,c in pairs:
        if maybe(0.5):
            t=re.sub(pat, random.choice(c) if isinstance(c,(list,tuple)) else c, t, flags=re.I)
    return t
REPL={
"biz_quote":[(r"報價|詢價","報價單"),(r"估算|試算",["估算","試算"]),(r"\bquote\b|\bpricing\b","quote"),(r"總價","總額"),(r"年費","年度授權"),(r"\bTCO\b","TCO")],
"tech_support":[(r"\bUAT\b","UAT"),(r"\bprod(uction)?\b","prod"),(r"sandbox","sandbox"),(r"\bAPI\b","API"),(r"\b(429|500)\b",["429","500"]),(r"OTP","OTP"),(r"SSO|SAML","SSO"),(r"CORS","CORS")],
"policy_qa":[(r"退款|退費","退費"),(r"提前終止|終止合約","提前終止"),(r"條款|政策","條款"),(r"\bcredit note\b","credit note"),(r"\bvoid\b","void"),(r"SLA|違約金","SLA")],
"profile_update":[(r"更新|變更","更新"),(r"新增|加到","新增"),(r"白名單\s*IP","白名單 IP"),(r"寄送地址|收件地址","寄送地址"),(r"發票抬頭","發票抬頭")],
"complaint":[(r"延期|延宕","延宕"),(r"沒有更新|久未處理","沒有更新"),(r"請提供\s*ETA","請提供 ETA"),(r"不一致|衝突","不一致"),(r"排程|時程","時程")],
"other":[(r"簡介|概覽|介紹","簡介"),(r"成功案例|案例","成功案例"),(r"Roadmap|roadmap","Roadmap"),(r"不急著報價|暫不需要價格","暫不需要價格")]}
def add_prefix(t):
    if maybe(0.3):
        pre=["Re: ","Fwd: "][np.random.randint(2)]
        if not t.startswith(pre): t=pre+t
    return t
def noise(t):
    import re
    if maybe(0.3): t=re.sub(r"\s{2,}"," ",t)
    if maybe(0.3): t=t.replace("，",",").replace("。",".")
    if maybe(0.2): t=re.sub(r"\bEOD\b",["EOD","EOW"][np.random.randint(2)],t)
    return t
def touch_amt(t):
    import re
    if "<AMOUNT>" in t and maybe(0.7):
        t=re.sub(r"(NT\$|USD|US\$)?\s*<AMOUNT>", np.random.choice(["NT$<AMOUNT>","NT$ <AMOUNT>","USD <AMOUNT>","US$ <AMOUNT>"]), t)
    return t
def trailer(t,lab,lang):
    if maybe(0.25):
        add={
        ("biz_quote","zh"):" 請一併提供折扣後總額與付款條件。",
        ("tech_support","zh"):" 請提供修復 ETA 與 workaround。",
        ("policy_qa","zh"):" 也請附上正式政策文件連結 <URL>。",
        ("profile_update","zh"):" 生效時間為下個計費週期。",
        ("complaint","zh"):" 若無具體計畫，我們將延後上線。",
        ("other","zh"):" 目前只需功能概覽與案例。",
        ("biz_quote","en"):" Please include discount and payment terms.",
        ("tech_support","en"):" Please share ETA and a temporary workaround.",
        ("policy_qa","en"):" A link to the official policy <URL> would help.",
        ("profile_update","en"):" Effective next billing cycle.",
        ("complaint","en"):" We may postpone go-live without a concrete plan.",
        ("other","en"):" Only a brief overview and case studies for now."}.get((lab,lang))
        if add: t+=add
    return t
def aug_row(r):
    t=r["text"]; lab=r["label"]; lang=r["meta"]["language"]
    return trailer(noise(touch_amt(swap(add_prefix(t), REPL[lab]))),lab,lang)
def auto_aug(base,mult=6,cap=3):
    out=[]; seq=20001
    for r in base:
        k=min(cap, max(1,mult//2))
        for _ in range(k):
            t=aug_row(r)
            o={"id":f"a-20250901-{seq:04d}","label":r["label"],"meta":{"language":r["meta"]["language"],"source":"auto_aug","confidence":1.0},"text":t}
            if okph(o["text"]): out.append(o); seq+=1
    return out
def rx_feat(texts,srcs):
    regs=[re.compile(p,re.I) for p in srcs]
    return csr_matrix(np.array([[1 if rx.search(t) else 0 for rx in regs] for t in texts],dtype=np.float32))
def train_svm_plus(rows,outdir,modelp):
    X=[r["text"] for r in rows]; y=[r["label"] for r in rows]
    sss=StratifiedShuffleSplit(n_splits=1,test_size=0.1,random_state=20250901); idx_tr,idx_te=next(sss.split(X,y))
    Xtr=[X[i] for i in idx_tr]; ytr=[y[i] for i in idx_tr]; Xte=[X[i] for i in idx_te]; yte=[y[i] for i in idx_te]
    sss2=StratifiedShuffleSplit(n_splits=1,test_size=0.1111,random_state=20250901); idx_tv,idx_va=next(sss2.split(Xtr,ytr))
    Xtv=[Xtr[i] for i in idx_tv]; ytv=[ytr[i] for i in idx_tv]; Xva=[Xtr[i] for i in idx_va]; yva=[ytr[i] for i in idx_va]
    rx=[
        r"\bAPI\b", r"/v\d+/", r"\bUAT\b", r"\bprod(uction)?\b", r"sandbox", r"\b(429|500)\b",
        r"OTP|SSO|SAML|CORS|webhook|TLS|限流|驗簽|白名單",
        r"報價|詢價|SOW|折扣|總價|TCO|PoC|授權|年費|一次性|試算|\bquote\b|\bpricing\b|USD|NT\$",
        r"退款|退費|提前終止|合約|條款|違約金|資料刪除|保留\s*90\s*天|升級|降級|\brefund|termination|policy|terms|credit note|void|retention|deletion|upgrade|downgrade",
        r"更新|變更|改為|新增|刪除|白名單\s*IP|寄送地址|收件人|發票抬頭|\bupdate|billing email|recipient|whitelist",
        r"等太久|困擾|太慢|不一致|沒動靜|延宕|抱怨|正面回應|\bfrustrated|concerns|inconsistent|delay|outage|no update|escalat(e|ion)|realistic ETA"
    ]
    char=TfidfVectorizer(analyzer="char_wb",ngram_range=(3,5),min_df=1); word=TfidfVectorizer(analyzer="word",ngram_range=(1,2),min_df=1)
    Xc_tr=char.fit_transform(Xtv); Xw_tr=word.fit_transform(Xtv); Xr_tr=rx_feat(Xtv,rx)
    Xc_va=char.transform(Xva); Xw_va=word.transform(Xva); Xr_va=rx_feat(Xva,rx)
    Xtr_all=hstack([Xc_tr,Xw_tr,Xr_tr]); Xva_all=hstack([Xc_va,Xw_va,Xr_va])
    cnt=Counter(ytv); mx=max(cnt.values()); Xtv_bal=[]; ytv_bal=[]
    for lab in sorted(cnt):
        idx=[i for i,z in enumerate(ytv) if z==lab]; need=mx-len(idx); pick=idx+[idx[np.random.randint(len(idx))] for _ in range(need)]
        Xtv_bal.append(hstack([char.transform([Xtv[i] for i in pick]),word.transform([Xtv[i] for i in pick]),rx_feat([Xtv[i] for i in pick],rx)])); ytv_bal+= [lab]*len(pick)
    Xtv_bal=vstack(Xtv_bal)
    best=0; bestC=1
    for C in [0.5,1,2,4]:
        clf=LinearSVC(C=C,class_weight="balanced").fit(Xtv_bal,ytv_bal)
        rep=classification_report(yva, clf.predict(Xva_all), labels=LABELS, digits=3, zero_division=0, output_dict=True)
        mf=rep["macro avg"]["f1-score"]
        if mf>best: best=mf; bestC=C
    Xc_tv=char.fit_transform(Xtr); Xw_tv=word.fit_transform(Xtr); Xr_tv=rx_feat(Xtr,rx); Xtv_all=hstack([Xc_tv,Xw_tv,Xr_tv])
    final=LinearSVC(C=bestC,class_weight="balanced").fit(Xtv_all,ytr)
    Xc_te=char.transform(Xte); Xw_te=word.transform(Xte); Xr_te=rx_feat(Xte,rx); Xte_all=hstack([Xc_te,Xw_te,Xr_te])
    import pickle,os
    with open(modelp,"wb") as f: pickle.dump({"clf":final,"char_vec":char,"word_vec":word,"regex_sources":rx},f)
    REP.mkdir(parents=True,exist_ok=True)
    (REP/"val_report.txt").write_text(classification_report(yva, LinearSVC(C=bestC,class_weight="balanced").fit(Xtv_bal,ytv_bal).predict(Xva_all), labels=LABELS, digits=3, zero_division=0),encoding="utf-8")
    (REP/"test_report.txt").write_text(classification_report(yte, final.predict(Xte_all), labels=LABELS, digits=3, zero_division=0),encoding="utf-8")
    cm=confusion_matrix(yte, final.predict(Xte_all), labels=LABELS)
    with (REP/"confusion_matrix.tsv").open("w",encoding="utf-8") as f:
        f.write("\t"+"\t".join(LABELS)+"\n")
        for i,row in enumerate(cm): f.write(LABELS[i]+"\t"+"\t".join(map(str,row))+"\n")
    print("[SAVED]",modelp)
base=R(FULL); hc=R(HC); cb=R(CB)
assert base, "missing base dataset"
def build():
    auto=auto_aug(base,mult=6,cap=3)
    seen=set(); clean=[]
    for r in base+hc+cb+auto+cb:
        if not okph(r["text"]): continue
        k=(r["label"], r["meta"]["language"], normk(r["text"]))
        if k in seen: continue
        seen.add(k); clean.append(r)
    W(auto,AUTO); W(clean,MERG)
    labels=[r["label"] for r in clean]
    sss=StratifiedShuffleSplit(n_splits=1,test_size=0.1,random_state=20250901); idx_tr,idx_te=next(sss.split(clean,labels))
    rest=[clean[i] for i in idx_tr]; test=[clean[i] for i in idx_te]
    sss2=StratifiedShuffleSplit(n_splits=1,test_size=0.1111,random_state=20250901); lr=[r["label"] for r in rest]; idx_tv,idx_va=next(sss2.split(rest,lr))
    train_rows=[rest[i] for i in idx_tv]; val_rows=[rest[i] for i in idx_va]
    SPLT.mkdir(parents=True,exist_ok=True); W(train_rows,SPLT/"train.jsonl"); W(val_rows,SPLT/"val.jsonl"); W(test,SPLT/"test.jsonl")
    print("[SPLIT]",len(train_rows),len(val_rows),len(test))
    print("[DIST]",Counter([r["label"] for r in clean]))
    train_svm_plus(rows=clean,outdir=REP,modelp=ART)
print("[BASE]",len(base),"[HC]",len(hc),"[CB]",len(cb)); build()
