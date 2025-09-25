import os, json, sys, time
from pathlib import Path

KIE_DIR = Path(os.getenv("KIE_DIR", "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model"))
CANDS = [
  Path(os.getenv("KIE_EVAL_DATA","")),
  Path("data/kie/test_real.for_eval.jsonl"),
  Path("/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/test_real.for_eval.jsonl"),
  Path("data/kie/test.jsonl"),
]
DATA = next((p for p in CANDS if p and p.exists()), None)
OUTD = Path("reports_auto/kie")/time.strftime("%Y%m%dT%H%M%S")
OUTD.mkdir(parents=True, exist_ok=True)

def read_jsonl(p:Path):
    for line in p.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line: continue
        yield json.loads(line)

def get_gold(obj):
    # 支援多格式：entities/spans/labels，每個 span 至少要 {label|type, start, end}
    spans = obj.get("entities") or obj.get("spans") or obj.get("labels") or []
    out=[]
    for s in spans:
        lab = s.get("label") or s.get("type")
        st  = s.get("start"); ed=s.get("end")
        if lab is None or st is None or ed is None: continue
        out.append((lab,int(st),int(ed)))
    return out

def pred_spans(text:str):
    import torch
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    tok = AutoTokenizer.from_pretrained(KIE_DIR, use_fast=True)
    mdl = AutoModelForTokenClassification.from_pretrained(KIE_DIR)
    mdl.eval()
    enc = tok(text, return_offsets_mapping=True, return_tensors="pt", truncation=True)
    offsets = enc.pop("offset_mapping")[0].tolist()
    with torch.no_grad():
        logits = mdl(**enc).logits[0]
    # same spanizer as shim
    import torch
    probs = torch.softmax(logits, dim=-1)
    idx   = torch.argmax(probs, dim=-1).tolist()
    id2 = mdl.config.id2label
    labels = [id2.get(i,str(i)) for i in idx]
    out=[]; cur=None
    for lab,(s,e) in zip(labels, offsets):
        if (s,e)==(0,0): continue
        if lab and lab!="O":
            if cur and cur[0]==lab and s==cur[1]:
                cur=(lab,cur[1],e)
            else:
                if cur: out.append(cur); cur=None
                cur=(lab,s,e)
        else:
            if cur: out.append(cur); cur=None
    if cur: out.append(cur)
    return out

def exact_prf1(golds,preds):
    G=set(golds); P=set(preds)
    tp=len(G & P); fp=len(P - G); fn=len(G - P)
    prec=tp/(tp+fp) if tp+fp else 0.0
    rec =tp/(tp+fn) if tp+fn else 0.0
    f1 =2*prec*rec/(prec+rec) if prec+rec else 0.0
    return dict(tp=tp,fp=fp,fn=fn,precision=prec,recall=rec,f1=f1)

def iou(a,b):
    # a,b: (lab, start, end) ; same label才算
    la,sa,ea=a; lb,sb,eb=b
    if la!=lb: return 0.0
    inter=max(0, min(ea,eb)-max(sa,sb))
    union=max(ea,eb)-min(sa,sb)
    return inter/union if union>0 else 0.0

def partial_prf1(golds,preds,thr=0.5):
    G=list(golds); P=list(preds)
    matched=set(); tp=0
    for i,g in enumerate(G):
        best=-1; bestj=-1
        for j,p in enumerate(P):
            if j in matched: continue
            ov=iou(g,p)
            if ov>best: best=ov; bestj=j
        if best>=thr and bestj>=0:
            matched.add(bestj); tp+=1
    fp=len(P)-len(matched); fn=len(G)-tp
    prec=tp/(tp+fp) if tp+fp else 0.0
    rec =tp/(tp+fn) if tp+fn else 0.0
    f1 =2*prec*rec/(prec+rec) if prec+rec else 0.0
    return dict(tp=tp,fp=fp,fn=fn,precision=prec,recall=rec,f1=f1,threshold=thr)

def main():
    if DATA is None:
        (OUTD/"_WARN.txt").write_text("No eval dataset found.\n",encoding="utf-8")
        print("[WARN] no dataset; set KIE_EVAL_DATA=/path/to/*.jsonl", file=sys.stderr)
        return 0
    N=0; Gall=[]; Pall=[]
    samples=[]
    for obj in read_jsonl(DATA):
        txt=obj.get("text") or obj.get("content") or obj.get("raw") or ""
        if not txt: continue
        g=get_gold(obj); p=pred_spans(txt)
        Gall.extend(g); Pall.extend(p); N+=1
        if len(samples)<5:
            samples.append({"text":txt[:120], "golds":g, "preds":p})
    exact=exact_prf1(Gall,Pall); partial=partial_prf1(Gall,Pall,0.5)
    out={"dataset":str(DATA), "n_docs":N, "exact":exact, "partial@0.5":partial, "samples":samples}
    (OUTD/"metrics.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    md = [ "# KIE Eval (span-level)\n",
           f"- dataset: `{DATA}`\n",
           f"- docs: {N}\n",
           "## Exact match\n",
           f"- P: {exact['precision']:.3f}  R: {exact['recall']:.3f}  F1: **{exact['f1']:.3f}**\n",
           "## Partial (IoU≥0.5)\n",
           f"- P: {partial['precision']:.3f}  R: {partial['recall']:.3f}  F1: **{partial['f1']:.3f}**\n"]
    (OUTD/"metrics.md").write_text("".join(md),encoding="utf-8")
    print("[OK] KIE eval ->", OUTD)
if __name__=="__main__": main()
