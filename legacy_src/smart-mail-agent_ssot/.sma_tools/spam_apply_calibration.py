#!/usr/bin/env python3
import argparse, json, math
def sigmoid(x):
    try:
        v=float(x)
        if 0.0<=v<=1.0: return v
        return 1/(1+math.exp(-v))
    except: return None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("-i","--in",required=True)
    ap.add_argument("-o","--out",required=True)
    ap.add_argument("-c","--calib",required=True)
    a=ap.parse_args()
    cfg=json.load(open(a.calib,encoding="utf-8"))
    name=cfg.get("score_name","score_text")
    n=upd=0
    with open(a.__dict__["in"],encoding="utf-8") as f, open(a.out,"w",encoding="utf-8") as g:
        for ln in f:
            if not ln.strip(): g.write(ln); continue
            o=json.loads(ln); sp=o.get("spam") or {}
            s=sigmoid(sp.get(name))
            if s is not None:
                sp["score_text"]=s; o["spam"]=sp; upd+=1
            n+=1; g.write(json.dumps(o,ensure_ascii=False)+"\n")
    print(f"[APPLY] name={name} n={n} updated={upd}")
if __name__=="__main__": main()
