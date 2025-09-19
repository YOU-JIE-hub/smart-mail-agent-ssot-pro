#!/usr/bin/env python3
import argparse, json, csv, re, hashlib, unicodedata, email.utils, datetime as dt
from pathlib import Path
WANTED={"subject","subject_norm","title","body","body_norm","content","text","text_norm","plain","raw_text",
        "message","snippet","summary","desc","description","from","to","date","time","ts"}
def norm(s):
    if s is None: return ""
    s=unicodedata.normalize("NFKC",str(s)).replace("\u3000"," ").lower()
    return re.sub(r"\s+"," ",s).strip()
def walk(o):
    out=[]; st=[o]; seen=0
    while st and seen<20000:
        seen+=1; cur=st.pop()
        if isinstance(cur,dict):
            for k,v in cur.items():
                if isinstance(v,str) and (k in WANTED or k.lower() in WANTED): out.append((k,v))
                elif isinstance(v,(dict,list)): st.append(v)
        elif isinstance(cur,list):
            for x in cur: st.append(x)
    return out
def mk_fp(subj,frm,date,body):
    s=f"{norm(subj)}||{norm(frm)}||{norm(date)}||{norm(body)[:2000]}"
    return hashlib.sha256(s.encode("utf-8","ignore")).hexdigest()[:16]
def ts_parse(x):
    if x is None: return None
    try:
        if isinstance(x,(int,float)): return float(x)
        xs=str(x).strip()
        if re.fullmatch(r"\d{10}(\.\d+)?",xs): return float(xs)
        try: return email.utils.parsedate_to_datetime(xs).timestamp()
        except: return dt.datetime.fromisoformat(xs.replace("Z","+00:00")).timestamp()
    except: return None
def load_jsonl(p):
    out=[]; P=Path(p)
    if not P.exists(): return out
    with P.open(encoding="utf-8",errors="ignore") as f:
        for ln in f:
            if ln.strip(): out.append(json.loads(ln))
    return out
def extract_core(o):
    d={k:"" for k in ["subject","from","to","date","body"]}
    for k,v in walk(o):
        kl=k.lower()
        if kl in ("subject","subject_norm","title"): d["subject"]=d["subject"] or v
        elif kl in ("from","sender"): d["from"]=d["from"] or v
        elif kl=="to": d["to"]=d["to"] or v
        elif kl in ("date","time","ts"): d["date"]=d["date"] or v
        elif kl in ("body","text","content","plain","raw_text","snippet","summary","description","message","body_norm","text_norm"):
            if len(d["body"])<2000: d["body"]=d["body"] or v
    return d
def jacc(a,b):
    A={}; B={}
    def grams(s):
        s=norm(s); 
        return {s[i:i+3] for i in range(max(0,len(s)-2))} if s else set()
    A=grams(a); B=grams(b)
    if not A or not B: return 0.0
    u=len(A|B); return (len(A&B)/u) if u else 0.0
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold",required=True); ap.add_argument("--pred",required=True)
    ap.add_argument("--pred_text"); ap.add_argument("--out",required=True)
    ap.add_argument("--fuzzy_threshold",type=float,default=0.90); ap.add_argument("--mode",default="auto")
    a=ap.parse_args()
    gold=load_jsonl(a.gold); pred=load_jsonl(a.pred)
    pred_text_map={}
    if a.pred_text:
        for o in load_jsonl(a.pred_text):
            pred_text_map[str(o.get("id",""))]=o
    P=[]
    for o in pred:
        pid=str(o.get("id","")); src=pred_text_map.get(pid,o)
        pc=extract_core(src); fp=mk_fp(pc["subject"],pc["from"],pc["date"],pc["body"])
        P.append((pid,pc,fp))
    P_by_id={pid:i for i,(pid,_,_) in enumerate(P)}; P_used=set()
    G=[]
    for o in gold:
        gid=str(o.get("id") or o.get("gold_id") or "")
        if not gid: continue
        gc=extract_core(o); gfp=o.get("gold_fp") or mk_fp(gc["subject"],gc["from"],gc["date"],gc["body"])
        G.append((gid,gc,gfp))
    mapping={}
    for gid,_,_ in G:
        if gid in P_by_id: mapping[gid]=(gid,"id",1.0); P_used.add(gid)
    for gid,gc,gfp in G:
        if gid in mapping: continue
        for pid,pc,fp in P:
            if pid in P_used: continue
            if fp==gfp: mapping[gid]=(pid,"fingerprint",1.0); P_used.add(pid); break
    def sim(gc,pc):
        s_sub=jacc(gc["subject"],pc["subject"]); s_body=jacc(gc["body"],pc["body"])
        s_from=1.0 if norm(gc["from"]) and norm(gc["from"])==norm(pc["from"]) else 0.0
        s_to  =1.0 if norm(gc["to"])   and norm(gc["to"])  ==norm(pc["to"])   else 0.0
        tg, tp = ts_parse(gc["date"]), ts_parse(pc["date"])
        bonus=0.05 if (tg and tp and abs(tg-tp)<=3*24*3600) else 0.0
        return 0.5*s_sub+0.4*s_body+0.05*s_from+0.05*s_to+bonus
    TH=a.fuzzy_threshold
    for gid,gc,_ in G:
        if gid in mapping: continue
        best=("",-1.0)
        for pid,pc,_ in P:
            if pid in P_used: continue
            sc=sim(gc,pc); 
            if sc>best[1]: best=(pid,sc)
        if best[0] and best[1]>=TH:
            mapping[gid]=(best[0],"fuzzy",float(f"{best[1]:.4f}")); P_used.add(best[0])
    G_rem=[gid for gid,_,_ in G if gid not in mapping]
    P_rem=[pid for pid,_,_ in P if pid not in P_used]
    for gid,pid in zip(G_rem,P_rem): mapping[gid]=(pid,"order",0.0); P_used.add(pid)
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["gold_id","pred_id","method","similarity"])
        for gid,(pid,method,sc) in mapping.items(): w.writerow([gid,pid,method,sc if isinstance(sc,str) else f"{sc:.4f}"])
    total=len(G); matched=len(mapping); cov=matched/total if total else 0.0
    summ=Path("reports_auto/alignment/ALIGN_SUMMARY.txt"); summ.parent.mkdir(parents=True,exist_ok=True)
    summ.write_text(f"TOTAL_GOLD={total}\nMATCHED={matched}\nCOVERAGE={cov:.4f}\nOUT={out}\n",encoding="utf-8")
    print(f"TOTAL_GOLD={total}\nMATCHED={matched}\nCOVERAGE={cov:.4f}\nOUT={out}")
if __name__=="__main__": main()
