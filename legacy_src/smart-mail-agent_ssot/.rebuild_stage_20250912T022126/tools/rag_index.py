from __future__ import annotations
from pathlib import Path
import json, math, re, time, argparse

def tokenize(s:str)->list[str]:
    try:
        import regex as rx
        return [t.lower() for t in rx.findall(r'\p{L}[\p{L}\p{M}\p{N}_]*|\p{N}+', s)]
    except Exception:
        return [t.lower() for t in re.findall(r'\w+', s, flags=re.UNICODE)]

def load_docs(kb_dir:Path):
    docs=[]
    for p in sorted(kb_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".md",".txt"}:
            txt=p.read_text("utf-8", errors="ignore")
            tit=txt.splitlines()[0].lstrip("# ").strip() if txt.strip() else p.stem
            docs.append((p, tit, txt))
    return docs

def build_index(kb_dir:str, out_path:str):
    kb=Path(kb_dir); docs=load_docs(kb)
    N=len(docs); 
    if N==0:
        Path(out_path).write_text(json.dumps({"N":0,"docs":{},"df":{},"avgdl":0.0,"built_at":time.time()}, ensure_ascii=False, indent=2), "utf-8")
        print("[OK] index empty ->", out_path); return
    df={}; inv_docs={}
    total_len=0
    for p,tit,txt in docs:
        toks=tokenize(txt)
        total_len+=len(toks)
        tf={}
        for t in toks: tf[t]=tf.get(t,0)+1
        for t in tf: df[t]=df.get(t,0)+1
        inv_docs[p.name]={"tf":tf,"len":len(toks),"title":tit,"snippet":(txt[:240].replace("\n"," ")+"…")}
    avgdl=total_len/float(N)
    index={"N":N,"df":df,"docs":inv_docs,"avgdl":avgdl,"built_at":time.time()}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(index, ensure_ascii=False), "utf-8")
    print(f"[OK] index -> {out_path}  N={N} avgdl={avgdl:.1f}")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--kb-dir", default="kb/faq")
    ap.add_argument("--out", default="kb/index.json")
    a=ap.parse_args()
    build_index(a.kb_dir, a.out)
