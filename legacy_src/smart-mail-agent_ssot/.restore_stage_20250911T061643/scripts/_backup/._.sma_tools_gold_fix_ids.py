#!/usr/bin/env python3
import argparse, json, re, hashlib, unicodedata
from pathlib import Path
def norm(s):
    if s is None: return ""
    s = unicodedata.normalize("NFKC", str(s)).replace("\u3000"," ").lower()
    return re.sub(r"\s+"," ",s).strip()
WANTED={"subject","title","content","body","text","plain","raw_text","snippet","summary","description",
        "subject_norm","body_norm","text_norm"}
def walk_strings(o):
    out=[]; stack=[o]; seen=0
    while stack and seen<20000:
        cur=stack.pop(); seen+=1
        if isinstance(cur,dict):
            for k,v in cur.items():
                if isinstance(v,str) and (k in WANTED or k.lower() in WANTED): out.append(v)
                elif isinstance(v,(dict,list)): stack.append(v)
        elif isinstance(cur,list):
            for x in cur:
                if isinstance(x,(dict,list)): stack.append(x)
                elif isinstance(x,str): out.append(x)
    return out
def mk_fp(o):
    subj=(o.get("subject") or o.get("subject_norm") or "")
    frm =(o.get("from") or o.get("sender") or "")
    date=(o.get("date") or o.get("ts") or o.get("time") or "")
    body="\n".join(walk_strings(o))[:2000]
    s=f"{norm(subj)}||{norm(frm)}||{norm(date)}||{norm(body)}"
    return hashlib.sha256(s.encode("utf-8","ignore")).hexdigest()[:16]
def find_id(o):
    for k in ("id","corr_id","gold_id","message_id","uid"):
        v=o.get(k)
        if isinstance(v,(str,int)) and str(v).strip(): return str(v)
    m=re.search(r"\bi-\d{8}-\d{3,6}\b", json.dumps(o,ensure_ascii=False))
    return m.group(0) if m else None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in","-i",required=True); ap.add_argument("--out","-o",required=True)
    a=ap.parse_args()
    src=Path(a.__dict__["in"]); dst=Path(a.out)
    total=fixed=0
    with src.open(encoding="utf-8",errors="ignore") as f, dst.open("w",encoding="utf-8") as g:
        for ln in f:
            if not ln.strip(): continue
            total+=1; o=json.loads(ln)
            i=find_id(o)
            if i: o["id"]=i; fixed+=1
            o.setdefault("gold_fp", mk_fp(o))
            g.write(json.dumps(o,ensure_ascii=False)+"\n")
    print(f"[GOLD_FIX] total={total} fixed={fixed} OUT={dst}")
if __name__=="__main__": main()
