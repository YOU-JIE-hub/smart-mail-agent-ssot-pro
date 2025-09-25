#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys, re, datetime
from pathlib import Path

# --- pickle 相容（Intent rules_feat/ZeroPad/DictFeaturizer）---
try:
    from .sma_tools.train_pro_fresh import rules_feat as _real_rules_feat  # type: ignore
except Exception:
    _real_rules_feat = None
def rules_feat(x):
    if _real_rules_feat is not None:
        try: return _real_rules_feat(x)
        except Exception: pass
    return {}
class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features=int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X):
        from scipy import sparse as sp
        return sp.csr_matrix((len(X), self.n_features), dtype="float64")
class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X):
        from scipy import sparse as sp
        return sp.csr_matrix((len(X), 0), dtype="float64")

def read_jsonl(path): 
    p=Path(path)
    if not p.exists(): return []
    out=[]
    for ln in p.read_text(encoding="utf-8",errors="ignore").splitlines():
        s=ln.strip()
        if not s: continue
        try: out.append(json.loads(s))
        except: continue
    return out
def write_jsonl(path, rows):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w",encoding="utf-8") as w:
        for r in rows: w.write(json.dumps(r,ensure_ascii=False)+"\n")

# --- Spam ---
def spam_load(model_fp, thr_fp):
    import joblib
    obj=joblib.load(model_fp)
    if isinstance(obj, dict) and "vect" in obj and "cal" in obj:
        from sklearn.pipeline import Pipeline
        mdl=Pipeline([("vect",obj["vect"]),("cal",obj["cal"])])
    else:
        mdl=obj
    th=json.loads(Path(thr_fp).read_text(encoding="utf-8"))
    return mdl, float(th.get("threshold",0.44)), int(th.get("signals_min",3))
def spam_text_of(r): return (r.get("subject","")+"\n"+r.get("body",""))
def spam_signals(r):
    import re
    RE_URL=re.compile(r"https?://[^\s)>\]]+",re.I)
    SUS_TLD={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
    SUS_EXT={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
    KW=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
       "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]
    t=(r.get("subject","")+" "+r.get("body","")).lower()
    urls=RE_URL.findall(t); atts=[(a or "").lower() for a in r.get("attachments",[]) if a]
    s=0
    if urls: s+=1
    if any(u.lower().endswith(tld) for u in urls for tld in SUS_TLD): s+=1
    if any(k in t for k in KW): s+=1
    if any(a.endswith(ext) for a in atts for ext in SUS_EXT): s+=1
    if ("account" in t) and (("verify" in t) or ("reset" in t) or ("login" in t) or ("signin" in t)): s+=1
    if ("帳戶" in t) and (("驗證" in t) or ("重設" in t) or ("登入" in t)): s+=1
    return s
def spam_infer(model, thr, smin, items):
    import numpy as np
    X=[spam_text_of(r) for r in items]
    p=model.predict_proba(X)[:,1]
    y_text=(p>=thr).astype(int)
    sig=[spam_signals(r) for r in items]
    y_rule=(np.array(sig)>=smin).astype(int)
    y_ens=np.maximum(y_text,y_rule)
    out=[]
    for r,pp,pt,pr,pe,sg in zip(items,p,y_text,y_rule,y_ens,sig):
        out.append({"id":r.get("id",""),"score_text":float(pp),"signals":int(sg),
                    "pred_text":int(pt),"pred_rule":int(pr),"pred_ens":int(pe)})
    return out

# --- Intent ---
def intent_load(model_fp, thr_fp):
    import joblib
    mdl=joblib.load(model_fp)
    cfg=json.loads(Path(thr_fp).read_text(encoding="utf-8"))
    return mdl, cfg
def intent_route(model, cfg, items):
    import subprocess, pathlib, numpy as np
    if not hasattr(model,"predict_proba"):
        tmp=pathlib.Path("reports_auto/_tmp_e2e"); tmp.mkdir(parents=True,exist_ok=True)
        inp=tmp/"intent_input.jsonl"; outp=tmp/"intent_preds.jsonl"
        with inp.open("w",encoding="utf-8") as w:
            for r in items: w.write(json.dumps({"id":r.get("id",""),"subject":r.get("subject",""),"body":r.get("body","")},ensure_ascii=False)+"\n")
        router=None
        for c in (".sma_tools/runtime_threshold_router.py","reports_auto/intent/.sma_tools/runtime_threshold_router.py"):
            if pathlib.Path(c).exists(): router=c; break
        if router is None: raise FileNotFoundError("runtime_threshold_router.py not found")
        cmd=[sys.executable,router,"--model","artifacts/intent_pro_cal.pkl","--input",str(inp),
             "--config","reports_auto/intent_thresholds.json","--out_preds",str(outp)]
        subprocess.run(cmd,check=True)
        preds=[]
        for ln in outp.read_text(encoding="utf-8",errors="ignore").splitlines():
            if not ln.strip(): continue
            try: o=json.loads(ln)
            except: continue
            fin = o.get("final") or o.get("pred") or o.get("label") or o.get("top") or "other"
            top = o.get("top")   or o.get("label") or o.get("pred") or fin
            p1v = o.get("p1")    or o.get("score") or 0.0
            gap = o.get("gap")   or 0.0
            preds.append({"id":o.get("id",""),"top":top,"p1":float(p1v),"gap":float(gap),"final":fin})
        return preds
    X=[(r.get("subject","")+"\n"+r.get("body","")) for r in items]
    proba=model.predict_proba(X)
    labels=model.classes_.tolist()
    p1=float(cfg.get("p1",0.5)); margin=float(cfg.get("margin",0.1)); lock=bool(cfg.get("policy_lock",True))
    out=[]
    for r,pp in zip(items,proba):
        idx=int(pp.argmax()); top=labels[idx]; top_p=float(pp[idx])
        sidx=pp.argsort()[::-1]; gap=float(pp[sidx[0]]-pp[sidx[1]]) if len(pp)>1 else 1.0
        final=top
        if lock and top!="policy_qa" and ("policy_qa" in labels):
            pol=labels.index("policy_qa")
            if float(pp[pol])>0.45 and (len(pp)<2 or float(pp[pol])>float(pp[sidx[1]])): final="policy_qa"
        if (top_p<p1) or (gap<margin): final="other"
        out.append({"id":r.get("id",""),"top":top,"p1":top_p,"gap":gap,"final":final})
    return out

# --- KIE ---
def kie_load(model_dir):
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    tok=AutoTokenizer.from_pretrained(model_dir)
    import torch
    mdl=AutoModelForTokenClassification.from_pretrained(model_dir).eval()
    cfg=mdl.config
    labels=None; num=getattr(cfg,"num_labels",None)
    if isinstance(getattr(cfg,"id2label",None),(list,tuple)) and cfg.id2label:
        labels=list(cfg.id2label); num=len(labels) if num is None else num
    elif isinstance(getattr(cfg,"id2label",None),dict) and cfg.id2label:
        inv={}
        for k,v in cfg.id2label.items():
            try: inv[int(k)]=v
            except: pass
        if inv:
            if num is None: num=max(inv.keys())+1
            labels=["O"]*int(num)
            for i,lab in inv.items():
                if 0<=i<len(labels): labels[i]=lab
    if labels is None and isinstance(getattr(cfg,"label2id",None),dict) and cfg.label2id:
        inv={}
        for lab,idx in cfg.label2id.items():
            try: inv[int(idx)]=lab
            except: pass
        if inv:
            if num is None: num=max(inv.keys())+1
            labels=["O"]*int(num)
            for i,lab in inv.items():
                if 0<=i<len(labels): labels[i]=lab
    if labels is None: labels=["O"]
    return tok, mdl, labels
def kie_extract(tok, mdl, id2list, text, max_len=512):
    import torch
    enc=tok(text, return_offsets_mapping=True, truncation=True, max_length=max_len)
    with torch.no_grad():
        lg=mdl(torch.tensor([enc["input_ids"]]), attention_mask=torch.tensor([enc["attention_mask"]])).logits[0]
    ids=lg.argmax(-1).tolist()
    labs=[id2list[i] if i<len(id2list) else "O" for i in ids]
    spans=[]; cur=None
    for lab,(st,ed) in zip(labs, enc["offset_mapping"]):
        if (st,ed)==(0,0) or lab=="O":
            if cur is not None: spans.append(cur); cur=None; continue
            else: continue
        if lab.startswith("B-"):
            if cur is not None: spans.append(cur)
            cur={"label":lab[2:],"start":int(st),"end":int(ed)}
        elif lab.startswith("I-") and cur is not None and cur["label"]==lab[2:]:
            cur["end"]=int(ed)
        else:
            if cur is not None: spans.append(cur); cur=None
    if cur is not None: spans.append(cur)
    out=[]; last=-1
    for s in sorted(spans,key=lambda x:(x["start"],x["end"])):
        if s["start"]>=last: out.append(s); last=s["end"]
    return out

# --- 由 spans 取值 / 正規化 ---
def slice_by_span(text, s):
    a=int(s.get("start",0)); b=int(s.get("end",0))
    a=max(0, min(a, len(text))); b=max(a, min(b, len(text)))
    return text[a:b]
def norm_amount(s):
    # 回傳原字串與抽取數字（不拋例外）
    m=re.search(r'([A-Z]{3}|NT\\$|USD|EUR|TWD|HKD)?\\s*([\\d,]+(?:\\.\\d+)?)', s, re.I)
    if not m: return {"raw":s}
    cur=(m.group(1) or "").upper().replace("NT$","TWD")
    num=m.group(2).replace(",","")
    return {"raw":s, "currency":cur or None, "value":float(num)}
def norm_date(s):
    s=s.strip()
    m=re.match(r'(\\d{4})-(\\d{1,2})-(\\d{1,2})', s)
    if m:
        y,mn,d=m.groups()
        try: return {"raw":s,"iso":"%04d-%02d-%02d"%(int(y),int(mn),int(d))}
        except: return {"raw":s}
    m=re.match(r'(\\d{1,2})\\/(\\d{1,2})', s)  # 9/30 → 今年
    if m:
        y=datetime.date.today().year
        try: return {"raw":s,"iso":"%04d-%02d-%02d"%(int(y),int(m.group(1)),int(m.group(2)))}
        except: return {"raw":s}
    return {"raw":s}
def pack_fields(text, spans):
    out={}
    first={}
    for s in spans:
        lab=s.get("label")
        val=slice_by_span(text,s)
        if lab not in first: first[lab]=val
    if "amount" in first: out["amount"]=norm_amount(first["amount"])
    if "date_time" in first: out["date"]=norm_date(first["date_time"])
    if "env" in first: out["env"]=first["env"]
    if "sla" in first: out["sla"]=first["sla"]
    return out

# --- 決策整合（加入 fields） ---
def decide(spam, intent, kie_map, text_map):
    acts=[]
    sm_by_id={x["id"]:x for x in spam}
    for t in intent:
        mid=t["id"]; s=sm_by_id.get(mid, {"pred_ens":0})
        if int(s.get("pred_ens",0))==1:
            acts.append({"id":mid,"action":"quarantine","reason":"spam","fields":{}})
            continue
        fin=t["final"]
        if   fin=="biz_quote":      act="create_quote_ticket"
        elif fin=="tech_support":   act="create_support_ticket"
        elif fin=="complaint":      act="escalate_to_CX"
        elif fin=="policy_qa":      act="send_policy_docs"
        elif fin=="profile_update": act="update_profile"
        else:                       act="manual_triage"
        spans=kie_map.get(mid, [])
        fields=pack_fields(text_map.get(mid,""), spans) if spans else {}
        acts.append({"id":mid,"action":act,"fields":fields})
    return acts

def summarize(spam,intent,action,out_md):
    from collections import Counter
    ens=Counter(int(x.get("pred_ens",0)) for x in spam)
    acts=Counter(a["action"] for a in action)
    lines=[]
    lines.append("# E2E Summary")
    lines.append("")
    lines.append("## Spam（ENS 決策）")
    lines.append("- ENS=1（隔離）: "+str(ens.get(1,0)))
    lines.append("- ENS=0（通過）: "+str(ens.get(0,0)))
    lines.append("")
    lines.append("## Intent（final 路由分佈）")
    cnt={}
    for x in intent: cnt[x["final"]]=cnt.get(x["final"],0)+1
    for k in sorted(cnt.keys()): lines.append("- "+k+": "+str(cnt[k]))
    lines.append("")
    lines.append("## RPA Actions")
    for k,v in sorted(acts.items(), key=lambda kv:(-kv[1],kv[0])): lines.append("- "+k+": "+str(v))
    out_md.parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--kie_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    a=ap.parse_args()
    out=Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)

    cases=read_jsonl(a.cases)
    if not cases: cases=[{"id":"demo1","subject":"Need a quote","body":"Please quote NT$ 12,000 by 2025-09-30."}]
    text_map={r.get("id",""): (r.get("subject","")+"\n"+r.get("body","")) for r in cases}

    spam_m,thr,smin = spam_load("artifacts_prod/model_pipeline.pkl","artifacts_prod/ens_thresholds.json")
    intent_m,icfg   = intent_load("artifacts/intent_pro_cal.pkl","reports_auto/intent_thresholds.json")
    tok,mdl,id2     = kie_load(a.kie_dir)

    spam_pred   = spam_infer(spam_m, thr, smin, cases)
    intent_pred = intent_route(intent_m, icfg, cases)

    kie_dump=[]; kie_map={}
    for r in cases:
        mid=r.get("id","")
        text=text_map.get(mid,"")
        spans=kie_extract(tok, mdl, id2, text)
        kie_map[mid]=spans
        kie_dump.append({"id":mid,"spans":spans})

    actions=decide(spam_pred, intent_pred, kie_map, text_map)

    write_jsonl(out/"cases.jsonl",      cases)
    write_jsonl(out/"spam_pred.jsonl",  spam_pred)
    write_jsonl(out/"intent_pred.jsonl",intent_pred)
    write_jsonl(out/"kie_pred.jsonl",   kie_dump)
    write_jsonl(out/"actions.jsonl",    actions)
    summarize(spam_pred, intent_pred, actions, out/"SUMMARY.md")

    if cases:
        spans0=kie_map.get(cases[0].get("id",""),[])
        print("[SANITY] KIE spans on first case:", len(spans0))
    print("[OK] E2E outputs ->", out)
if __name__=="__main__": main()
