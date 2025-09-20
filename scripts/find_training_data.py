from __future__ import annotations
import os, re, json, csv, argparse, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter

ROOTS_DEFAULT = [
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]

IGNORE_DIR = {
    ".git","venv",".venv","dist","build","node_modules","artifacts","artifacts_prod",
    "artifacts_inbox","weights","models","reports_auto/logs","__pycache__"
}
DATA_EXT = {".jsonl",".json",".csv",".tsv"}
REPORT_HINT = re.compile(r"(train.*report|report\.json|MODEL_PATHS\.auto\.env|train_summary|canuse|summary)", re.I)

LABEL_KEYS = ["label","y","target","tag","class","category","intent","is_spam","spam"]
TEXT_KEYS  = ["text","body","content","message","subject","raw","input","email","mail"]

def norm_label(v):
    if isinstance(v, bool): return "spam" if v else "ham"
    s = str(v).strip()
    if s.lower() in {"1","true","spam","junk"}: return "spam"
    if s.lower() in {"0","false","ham","not_spam","legit"}: return "ham"
    return s

def walk_files(roots):
    for r in roots:
        r = Path(r)
        if not r.exists(): continue
        for p in r.rglob("*"):
            try:
                if not p.is_file(): continue
                if set(p.parts) & IGNORE_DIR: continue
                yield p
            except Exception:
                continue

def is_dataset_file(p: Path) -> bool:
    if p.suffix.lower() in DATA_EXT: return True
    name = p.name.lower()
    if any(k in name for k in ["dataset","train","data","spam","intent"]):
        if p.suffix.lower()==".txt" and p.stat().st_size>100_000:
            return True
    return False

def is_report_file(p: Path) -> bool:
    return bool(REPORT_HINT.search(p.as_posix()))

def sha256_head(path: Path, n_bytes=1<<20) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(n_bytes))
    return h.hexdigest()

def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ln=ln.strip()
            if not ln: continue
            try:
                o=json.loads(ln)
            except Exception:
                continue
            y=None
            for k in LABEL_KEYS:
                if k in o:
                    y=norm_label(o[k]); break
            if y is None: 
                continue
            x=None
            for k in TEXT_KEYS:
                if k in o and isinstance(o[k],str) and o[k].strip():
                    x=o[k]; break
            if x is None:
                xs=[str(v) for _,v in o.items() if isinstance(v,str)]
                x=" ".join(xs) if xs else None
            if x: yield x, y

def iter_json(path: Path):
    try:
        obj=json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return
    rows=[]
    if isinstance(obj,list): it=obj
    elif isinstance(obj,dict):
        it=obj.get("data") or obj.get("items") or []
    else:
        it=[]
    for o in it:
        if not isinstance(o,dict): continue
        y=None
        for k in LABEL_KEYS:
            if k in o: y=norm_label(o[k]); break
        if y is None: continue
        x=None
        for k in TEXT_KEYS:
            if k in o and isinstance(o[k],str) and o[k].strip():
                x=o[k]; break
        if x is None:
            xs=[str(v) for _,v in o.items() if isinstance(v,str)]
            x=" ".join(xs) if xs else None
        if x: rows.append((x,y))
    for r in rows: yield r

def iter_csv(path: Path, delim=","):
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            rd=csv.DictReader(f, delimiter=delim)
            for o in rd:
                y=None
                for k in LABEL_KEYS:
                    if k in o: y=norm_label(o[k]); break
                if y is None: continue
                x=None
                for k in TEXT_KEYS:
                    if k in o and isinstance(o[k],str) and o[k].strip():
                        x=o[k]; break
                if x is None:
                    xs=[str(v) for _,v in o.items() if isinstance(v,str)]
                    x=" ".join(xs) if xs else None
                if x: yield x,y
    except Exception:
        return

TOKEN_RE=re.compile(r"[A-Za-z0-9_]+", re.U)
def tokens_of_texts(texts, cap=200000):
    seen=set(); n=0
    for t in texts:
        for w in TOKEN_RE.findall(t.lower()):
            seen.add(w)
        n+=1
        if n>=cap: break
    return seen

def score_overlap(vocab:set, ds_tokens:set):
    if not vocab or not ds_tokens: return 0.0
    inter=len(vocab & ds_tokens)
    return inter / max(1,len(vocab))

def load_model_vocab_classes(pkl_path: str):
    vocab=set(); classes=set(); kind=None; err=None
    if not pkl_path: return {"vocab":vocab,"classes":classes,"kind":kind,"error":"no path"}
    try:
        import joblib, sys
        # shim 舊 pickled 名稱，避免 "Can't get attribute 'rules_feat*'"
        m = sys.modules.get("__main__")
        if m is not None:
            for nm in ["rules_feat","rules_feat_func","rules_features","rules_features_func"]:
                if not hasattr(m,nm):
                    setattr(m,nm, lambda x: {})
        obj = joblib.load(pkl_path)
        vec=None
        if hasattr(obj,"named_steps"):
            for step in obj.named_steps.values():
                if step.__class__.__name__.lower().startswith("tfidf"):
                    vec=step; break
        elif obj.__class__.__name__.lower().startswith("tfidf"):
            vec=obj
        if vec is not None and hasattr(vec,"vocabulary_"):
            vocab=set(vec.vocabulary_.keys())
        # classes
        if hasattr(obj,"classes_"):
            classes=set(map(str, obj.classes_))
        elif hasattr(obj,"named_steps"):
            last=list(obj.named_steps.values())[-1]
            if hasattr(last,"classes_"): classes=set(map(str,last.classes_))
        kind=obj.__class__.__name__
    except Exception as e:
        err=str(e)
    return {"vocab":vocab,"classes":classes,"kind":kind,"error":err}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", default=ROOTS_DEFAULT)
    ap.add_argument("--model-intent", default=os.environ.get("INTENT_PKL","models/intent/artifacts/model_pipeline.pkl"))
    ap.add_argument("--model-spam",   default=os.environ.get("SPAM_PKL","models/spam/artifacts/model_pipeline.pkl"))
    ap.add_argument("--outdir", default=None)
    args=ap.parse_args()

    ts=datetime.now().strftime("%Y%m%dT%H%M%S")
    outdir=Path(args.outdir or f"reports_auto/finddata_{ts}")
    outdir.mkdir(parents=True, exist_ok=True)

    intent_meta = load_model_vocab_classes(args.model_intent)
    spam_meta   = load_model_vocab_classes(args.model_spam)

    authoritative=set()
    reports=[]

    # 先從既有報告/環境檔拉出明示路徑
    for p in walk_files(args.roots):
        if not is_report_file(p): continue
        if p.suffix.lower()==".json":
            try:
                j=json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            cand=[]
            if isinstance(j,dict):
                for k in ["datasets","data","paths","selection","summary"]:
                    v=j.get(k)
                    if isinstance(v,dict):
                        for vv in v.values():
                            if isinstance(vv,str): cand.append(vv)
                    elif isinstance(v,list):
                        for it in v:
                            if isinstance(it,str): cand.append(it)
                # 全量掃一遍字串值
                for v in j.values():
                    if isinstance(v,str) and any(x in v for x in ("/data/","/dataset",".jsonl",".csv",".tsv",".json")):
                        cand.append(v)
            for cp in cand:
                pp=Path(cp)
                if pp.exists():
                    authoritative.add(str(pp.resolve()))
                    reports.append(str(p))
        elif p.name.endswith(".env") and "MODEL_PATHS" in p.name:
            try:
                for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if "=" in ln:
                        _,v=ln.split("=",1)
                        v=v.strip().strip('"').strip("'")
                        if any(s in v for s in (".jsonl",".csv",".tsv",".json")) and Path(v).exists():
                            authoritative.add(str(Path(v).resolve()))
                            reports.append(str(p))
            except Exception:
                pass

    # 掃描候選資料 + 與模型 vocab 交集分數
    candidates=[]
    for p in walk_files(args.roots):
        if not is_dataset_file(p): continue
        try:
            nbytes=p.stat().st_size
            if nbytes<50_000 or nbytes>600_000_000:  # 太小/太大跳過
                continue
        except Exception:
            continue

        ext=p.suffix.lower()
        rows=[]
        try:
            if ext==".jsonl":
                it=iter_jsonl(p)
            elif ext==".json":
                it=iter_json(p)
            elif ext in {".csv",".tsv"}:
                it=iter_csv(p, delim="," if ext==".csv" else "\t")
            else:
                continue
            for i,(x,y) in enumerate(it):
                rows.append((x,y))
                if i>=20000: break
        except Exception:
            continue
        if not rows: 
            continue

        X=[t for t,_ in rows]
        y=[str(l) for _,l in rows]
        lab=Counter(y)

        ds_tokens=set()
        for t in X[:20000]:
            for w in re.findall(r"[A-Za-z0-9_]+", t.lower()):
                ds_tokens.add(w)

        s_intent = score_overlap(intent_meta["vocab"], ds_tokens) if intent_meta["vocab"] else 0.0
        s_spam   = score_overlap(spam_meta["vocab"], ds_tokens)   if spam_meta["vocab"]   else 0.0

        candidates.append({
            "path": str(p.resolve()),
            "size_bytes": p.stat().st_size,
            "n": len(rows),
            "labels": lab,
            "sha256_head": sha256_head(p),
            "overlap": {"intent": s_intent, "spam": s_spam}
        })

    # 排名
    def pick_best(task):
        key=lambda c: (c["overlap"][task], c["n"], c["size_bytes"])
        return sorted(candidates, key=key, reverse=True)[:20]

    top_intent = pick_best("intent")
    top_spam   = pick_best("spam")

    def first_authoritative(toplist):
        for c in toplist:
            if c["path"] in authoritative:
                return c
        return toplist[0] if toplist else None

    best_intent = first_authoritative(top_intent)
    best_spam   = first_authoritative(top_spam)

    out = {
        "ts": ts,
        "models": {
            "intent": {"path": args.model_intent, "kind": intent_meta["kind"], "error": intent_meta["error"], "vocab_size": len(intent_meta["vocab"]), "classes": sorted(intent_meta["classes"])},
            "spam":   {"path": args.model_spam,   "kind": spam_meta["kind"],   "error": spam_meta["error"],   "vocab_size": len(spam_meta["vocab"]),   "classes": sorted(spam_meta["classes"])},
        },
        "authoritative_paths": sorted(list(authoritative)),
        "reports_considered": sorted(set(reports)),
        "top_intent": top_intent,
        "top_spam": top_spam,
        "best": {"intent": best_intent, "spam": best_spam},
    }

    outdir = Path(outdir)
    (outdir/"FINDINGS.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")

    def dump_tsv(name, rows):
        hdr = ["rank","path","n","labels","size_mb","overlap_intent","overlap_spam","sha256_head"]
        with (outdir/f"{name}.tsv").open("w", encoding="utf-8") as f:
            f.write("\t".join(hdr)+"\n")
            for i,c in enumerate(rows,1):
                f.write("\t".join([
                    str(i),
                    c["path"],
                    str(c["n"]),
                    json.dumps(c["labels"], ensure_ascii=False),
                    f"{c['size_bytes']/1024/1024:.2f}",
                    f"{c['overlap']['intent']:.4f}",
                    f"{c['overlap']['spam']:.4f}",
                    c["sha256_head"][:16],
                ])+"\n")
    dump_tsv("TOP_INTENT", top_intent)
    dump_tsv("TOP_SPAM", top_spam)

    envp = outdir/"DATA_PATHS.auto.env"
    with envp.open("w", encoding="utf-8") as f:
        if best_intent: f.write(f'INTENT_DATA="{best_intent["path"]}"\n')
        if best_spam:   f.write(f'SPAM_DATA="{best_spam["path"]}"\n')

    print("=== FINDDATA ===")
    print("OUT   :", outdir.as_posix())
    print("JSON  :", (outdir/"FINDINGS.json").as_posix())
    print("TSV   :", (outdir/"TOP_INTENT.tsv").as_posix(), (outdir/"TOP_SPAM.tsv").as_posix())
    print("BEST intent:", best_intent["path"] if best_intent else "(none)")
    print("BEST spam  :", best_spam["path"] if best_spam else "(none)")
    print("ENV   :", envp.as_posix())

if __name__ == "__main__":
    main()
