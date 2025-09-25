import json, pathlib, collections, time
SRC_DIR=pathlib.Path("data/raw")
OUT=pathlib.Path("reports_auto/data"); OUT.mkdir(parents=True, exist_ok=True)

def profile_one(p):
    n=0; lbl=collections.Counter(); dup=0; seen=set(); lens=[]
    for ln in p.read_text(encoding="utf-8",errors="ignore").splitlines():
        if not ln.strip(): continue
        row=json.loads(ln); txt=row.get("text",""); lab=row.get("label","")
        n+=1; lbl[lab]+=1; lens.append(len(txt))
        h=hash(txt); dup+= (1 if h in seen else 0); seen.add(h)
    return {"file":str(p),"n":n,"labels":dict(lbl),"dup":dup,"len_avg":(sum(lens)/len(lens)) if lens else 0}

def main():
    ts=time.strftime("%Y%m%dT%H%M%S"); md=OUT/(f"profile_{ts}.md")
    rows=[profile_one(p) for p in SRC_DIR.rglob("*.jsonl")]
    if not rows:
        text="# Data Profile\n\n(no raw data)\n"
        (OUT/"profile_latest.md").write_text(text, encoding="utf-8")
        md.write_text(text, encoding="utf-8")
        print("OUT:", md); return
    text="# Data Profile\n\n"
    for r in rows: text+=f"- {r['file']}: n={r['n']} dup={r['dup']} len_avg={r['len_avg']:.1f} labels={r['labels']}\n"
    (OUT/"profile_latest.md").write_text(text, encoding="utf-8"); md.write_text(text, encoding="utf-8")
    print("OUT:", md)

if __name__=="__main__": main()
