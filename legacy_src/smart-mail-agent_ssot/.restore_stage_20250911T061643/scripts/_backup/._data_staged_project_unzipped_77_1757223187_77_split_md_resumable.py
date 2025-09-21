#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, sys, time, math, hashlib, json
from pathlib import Path

def human(n:int)->str:
    for u in ["B","KB","MB","GB","TB"]:
        if n<1024: return f"{n:.1f}{u}"
        n/=1024
    return f"{n:.1f}PB"

def parse_size(s:str)->int:
    s=s.strip().lower()
    if s.endswith("k"): return int(s[:-1])*1024
    if s.endswith("m"): return int(s[:-1])*1024*1024
    if s.endswith("g"): return int(s[:-1])*1024*1024*1024
    return int(s)

def find_latest(root:Path)->Path|None:
    cand=sorted((root/"reports_auto"/"_refactor").glob("list_all_*.md"), key=lambda p:p.stat().st_mtime, reverse=True)
    if cand: return cand[0]
    cand=sorted(root.rglob("list_all_*.md"), key=lambda p:p.stat().st_mtime, reverse=True)
    return cand[0] if cand else None

def next_index(outdir:Path)->int:
    ex=sorted(outdir.rglob("part_*.md"))
    if not ex: return 0
    try: return int(ex[-1].stem.split("_")[-1])+1
    except: return 0

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/youjie/projects/smart-mail-agent")
    ap.add_argument("--src", default="")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--chunk-bytes", default="100k")
    ap.add_argument("--bucket", type=int, default=1000)
    ap.add_argument("--resume", action="store_true")
    a=ap.parse_args()

    root=Path(a.root).resolve()
    if not root.exists(): print(f"ERROR: 專案根不存在: {root}", file=sys.stderr); return 2
    src=Path(a.src) if a.src else find_latest(root)
    if not src or not src.exists(): print("ERROR: 找不到待切分的 list_all_*.md", file=sys.stderr); return 3

    chunk=parse_size(a.chunk_bytes)
    ts=time.strftime("%Y%m%dT%H%M%S")
    outdir=Path(a.outdir) if a.outdir else (root/"reports_auto"/"_refactor"/f"chunks_{ts}")
    outdir.mkdir(parents=True, exist_ok=True)

    state=outdir/".state.json"; index=outdir/"index.tsv"; sha=outdir/"sha256sum.txt"
    size=src.stat().st_size; total=math.ceil(size/chunk)
    print("SMA PRINT OK :: SPLIT START")
    print(f"SOURCE: {src}"); print(f"OUTDIR: {outdir}"); print(f"SIZE  : {size} bytes ({human(size)}), CHUNK={a.chunk_bytes}, TOTAL≈{total}")

    start_i=0; offset=0
    if state.exists():
        st=json.loads(state.read_text()); start_i=int(st.get("index",0)); offset=int(st.get("offset",0))
        print(f"RESUME: index={start_i}, offset={offset}")
    else:
        start_i=next_index(outdir); offset=start_i*chunk
        if start_i>0: print(f"RESUME (by parts): index={start_i}, offset≈{offset}")

    if not index.exists(): index.write_text("chunk_path\tsize_bytes\tline_count\n", encoding="utf-8")
    if not sha.exists(): sha.write_text("", encoding="utf-8")

    read=0
    with src.open("rb") as fin, index.open("a",encoding="utf-8") as idx, sha.open("a",encoding="utf-8") as shaf:
        if offset: fin.seek(offset); read=offset
        i=start_i; last=time.time()
        while read<size:
            bucket=outdir/f"bkt_{i//a.bucket:04d}"; bucket.mkdir(parents=True, exist_ok=True)
            part=bucket/f"part_{i:05d}.md"
            if part.exists() and part.stat().st_size>0:
                i+=1; read+=part.stat().st_size; continue
            to_read=min(chunk, size-read); data=fin.read(to_read)
            if not data: break
            h=hashlib.sha256(); h.update(data); part.write_bytes(data)
            lines=data.count(b"\n"); rel=part.relative_to(root).as_posix()
            idx.write(f"{rel}\t{len(data)}\t{lines}\n"); shaf.write(f"{h.hexdigest()}  {part.name}\n")
            read+=len(data); i+=1
            print(f"\rprogress: {i}/{total} ({read/size*100:5.1f}%)  wrote={rel}", end="", flush=True)
            if time.time()-last>1.2:
                idx.flush(); shaf.flush(); state.write_text(json.dumps({"index":i,"offset":read}), encoding="utf-8"); last=time.time()
    state.write_text(json.dumps({"index":i,"offset":read}), encoding="utf-8")
    print(f"\nSPLIT DONE :: {i-start_i} chunks"); print(f"INDEX={index}"); print(f"SHA256={sha}"); print("SMA PRINT OK :: SPLIT END"); return 0

if __name__=="__main__": sys.exit(main())
