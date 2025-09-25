#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json, hashlib, ast, time
from pathlib import Path
from collections import defaultdict

def eprint(x): print(x, file=sys.stderr, flush=True)
eprint("SMA PRINT OK :: SCAN START")

ROOT = Path(os.environ.get("SMA_ROOT", "/home/youjie/projects/smart-mail-agent")).resolve()
if not ROOT.exists() or not ROOT.is_dir():
    eprint(f"ERROR: 專案根不存在: {ROOT}"); sys.exit(2)
WRITE_OUT = os.environ.get("WRITE_OUT") == "1"
OUTDIR = ROOT / "reports_auto" / "_refactor"
if WRITE_OUT: OUTDIR.mkdir(parents=True, exist_ok=True)

EXTS = {".py",".sh",".md",".yml",".yaml",".toml",".json",".ini",""}
EXCLUDE_DIRS = {".git","venv",".venv","node_modules","dist","out","reports_auto",".sma_refactor_backups",".mypy_cache",".pytest_cache"}
ENTRY_PATTERNS = {"run_action_handler.py","action_handler.py","main.py","__main__.py","cli_spamcheck.py","sma_spamcheck.py","spamcheck.py","sma_e2e","run_pipeline"}

def want_file(p): return (p.suffix.lower() in EXTS) or (p.name=="Makefile")
def rel(p): 
    try: return p.relative_to(ROOT).as_posix()
    except Exception: return p.as_posix()

errors=[]

def sha256_file(p:Path):
    try:
        h=hashlib.sha256()
        with p.open("rb") as f:
            for b in iter(lambda:f.read(1<<20), b""):
                if not b: break
                h.update(b)
        return h.hexdigest()
    except Exception as ex:
        errors.append({"rel":rel(p),"stage":"sha256","error":str(ex)}); return None

def ast_sig(p:Path):
    if p.suffix.lower()!=".py": return ""
    try:
        t=ast.parse(p.read_text(encoding="utf-8",errors="ignore"))
        sig=[]
        for n in t.body:
            if isinstance(n, ast.FunctionDef): sig.append(f"def {n.name}({len(n.args.args)})")
            elif isinstance(n, ast.ClassDef): sig.append(f"class {n.name}")
            elif isinstance(n, ast.If): sig.append("if")
        return "|".join(sig)
    except Exception as ex:
        errors.append({"rel":rel(p),"stage":"ast","error":str(ex)}); return ""

def group_tag(r):
    if r.startswith("src/"): return "src"
    if r.startswith("examples/legacy"): return "legacy"
    if r.startswith("smart_mail_agent/") or r.startswith("ai_rpa/"): return "root_pkg"
    return "normal"

def is_entry(r:str)->bool:
    n=r.lower()
    return any(x in n for x in ENTRY_PATTERNS) or ("/cli/" in n) or ("/routing/" in n)

recs=[]; cnt=0
for dp, dns, fns in os.walk(ROOT, followlinks=False):
    dns[:]=[d for d in dns if d not in EXCLUDE_DIRS and not Path(dp,d).is_symlink()]
    for fn in fns:
        p=Path(dp,fn)
        if p.is_symlink() or not want_file(p): continue
        rp=rel(p)
        try: size=p.stat().st_size
        except Exception as ex: errors.append({"rel":rp,"stage":"stat","error":str(ex)}); size=-1
        recs.append({"rel":rp,"group":group_tag(rp),"sha256":sha256_file(p),"entry":is_entry(rp),"ast_sig":ast_sig(p),"size":size})
        cnt+=1
        if cnt%500==0: eprint(f"[scan] processed: {cnt}")

by_name=defaultdict(list)
for r in recs: by_name[Path(r["rel"]).name].append(r)

same=[]; diff=[]; entry=[]
for name, items in by_name.items():
    if len(items)>1 and any(i["entry"] for i in items): entry.append({"name":name,"items":items})
    buckets=defaultdict(list)
    for it in items: buckets[it["sha256"]].append(it)
    if len(items)>1 and len(buckets)==1: same.append({"name":name,"items":items})
    elif len(buckets)>1:
        asts=defaultdict(list)
        for it in items: asts[it["ast_sig"]].append(it)
        if len(asts)==1: same.append({"name":name,"items":items,"reason":"ast-equal"})
        else: diff.append({"name":name,"items":items})

summary={"ts":int(time.time()),"root":str(ROOT),"counts":{"total_files":len(recs),"entry_conflicts":len(entry),"same_content_groups":len(same),"diff_content_groups":len(diff),"errors":len(errors)}}

def dump(obj,name):
    if WRITE_OUT: (OUTDIR/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    else: print(json.dumps(obj,ensure_ascii=False))

dump(summary,"scan_summary.json")
if WRITE_OUT:
    dump(entry,"entry_conflicts.json")
    dump(same,"same_content.json")
    dump(diff,"diff_content.json")
    with (OUTDIR/"errors.jsonl").open("w",encoding="utf-8") as w:
        for e in errors: w.write(json.dumps(e,ensure_ascii=False)+"\n")

eprint(f"SMA PRINT OK :: SCAN DONE :: files={len(recs)} conflicts(entry={len(entry)}, same={len(same)}, diff={len(diff)}) errors={len(errors)}")
