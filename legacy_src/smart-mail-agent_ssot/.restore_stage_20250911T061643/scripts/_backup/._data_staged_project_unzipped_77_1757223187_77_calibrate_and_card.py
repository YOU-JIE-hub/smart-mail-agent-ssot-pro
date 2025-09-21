#!/usr/bin/env python3
import json, re, pickle, sys
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.metrics import classification_report, confusion_matrix

ROOT=Path(".")
MERG=ROOT/"data/intent/i_20250901_merged.jsonl"
FULL=ROOT/"data/intent/i_20250901_full.jsonl"
HC  =ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
CB  =ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
AUTO=ROOT/"data/intent/i_20250901_auto_aug.jsonl"
ART_BASE=ROOT/"artifacts/intent_svm_plus_auto.pkl"
ART_CAL =ROOT/"artifacts/intent_svm_plus_auto_cal.pkl"
REP_DIR =ROOT/"reports_auto"
LABELS=["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]

def read_jsonl(p):
    rows=[]
    if p.exists():
        with p.open("r",encoding="utf-8") as f:
            for ln in f:
                ln=ln.strip()
                if ln: rows.append(json.loads(ln))
    return rows

def rebuild_merged():
    PH={"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}
    def okph(t):
        toks=set(re.findall(r"<([A-Z_]+)>",t))
        return toks.issubset(PH)
    seen=set(); out=[]
    for p in [FULL,HC,CB,AUTO,MERG]:
        if p.exists():
            for ln in p.read_text(encoding="utf-8").splitlines():
                if not ln.strip(): continue
                r=json.loads(ln)
                if not okph(r.get("text","")): continue
                k=(r.get("label"), r.get("meta",{}).get("language"), r.get("text","").lower())
                if k in seen: continue
                seen.add(k); out.append(r)
    return out

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    mat=[[1 if rx.search(t) else 0 for rx in regs] for t in texts]
    return csr_matrix(np.array(mat, dtype=np.float32))

if not ART_BASE.exists():
    print("[FAIL] missing base model:", ART_BASE, file=sys.stderr); sys.exit(2)

bundle=pickle.load(open(ART_BASE,"rb"))
rows = read_jsonl(MERG) if MERG.exists() else rebuild_merged()
if not rows:
    print("[FAIL] no data to evaluate", file=sys.stderr); sys.exit(3)

texts=[r["text"] for r in rows]
y_true=[r["label"] for r in rows]
X=hstack([
    bundle["char_vec"].transform(texts),
    bundle["word_vec"].transform(texts),
    featurize_regex(texts, bundle["regex_sources"])
])

y_pred = bundle["clf"].predict(X)

REP_DIR.mkdir(parents=True, exist_ok=True)
rep_txt = classification_report(y_true, y_pred, labels=LABELS, digits=3, zero_division=0)
(REP_DIR/"cal_report.txt").write_text(rep_txt, encoding="utf-8")

cm=confusion_matrix(y_true, y_pred, labels=LABELS)
with (REP_DIR/"cal_confusion.tsv").open("w",encoding="utf-8") as f:
    f.write("\t"+"\t".join(LABELS)+"\n")
    for i,row in enumerate(cm):
        f.write(LABELS[i]+"\t"+"\t".join(map(str,row))+"\n")

out_bundle = dict(bundle)
out_bundle["calibrated"]="softmax_like"
with open(ART_CAL,"wb") as f:
    pickle.dump(out_bundle,f)

print("[SAVED]", ART_CAL)
print("[REPORT]", (REP_DIR/"cal_report.txt"))
