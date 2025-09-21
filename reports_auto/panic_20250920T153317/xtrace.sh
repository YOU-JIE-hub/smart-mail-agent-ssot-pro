+ CMD='
set -Eeuo pipefail

# 鎖定模型（你指定的 SPAM；INTENT 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={r"\.git$", r"venv$", r"\.venv$", r"dist$", r"build$", r"node_modules$", r"artifacts($|_)", r"weights$", r"models$", r"reports_auto/logs$", r"__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir_name(name:str)->bool:
    for pat in IGNORE:
        if re.search(pat, name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dirnames[:]=[d for d in dirnames if want_dir_name(d)]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f: h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore") if fp.suffix.lower()==".gz" \
           else fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    keys=["text","content","body","message","email","subject","title","content_text"]
    if isinstance(d,dict):
        for k in keys:
            v=d.get(k)
            if isinstance(v,str) and v.strip(): return v
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    return d if isinstance(d,str) else ""

def row_label(d):
    if isinstance(d,dict):
        for k in ["label","y","target","class","category","is_spam","spam"]:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                return str(v)
    return None

def load_model(path):
    try:
        m=joblib.load(path); return m, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

def take_vectorizer(pipe):
    try:
        steps=[]
        if hasattr(pipe,"named_steps"): steps+=list(pipe.named_steps.items())
        if hasattr(pipe,"steps"): steps+=list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer": return st
    except Exception: pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind":None, "error":err, "classes":None, "vocab_size":None, "steps":[]}
    if m is None: return meta, None, None
    meta["kind"]=m.__class__.__name__
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL") or os.environ.get("INTENT_PKL_DEFAULT")
SPAM_PKL=os.environ.get("SPAM_PKL")

intent_meta=intent_model=intent_vec=None
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta=spam_model=spam_vec=None
if SPAM_PKL and Path(SPAM_PKL).exists():
    spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL)

print(json.dumps({"models":{"intent":intent_meta,"spam":spam_meta}}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    ana = vec.build_analyzer(); vocab=set(vec.vocabulary_.keys()); seen=set()
    n=0; lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try: d=json.loads(line)
                    except Exception: continue
                    t=row_text(d); 
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d); 
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else (dt.get("data", []) or [])
            for d in rows[:max_rows]:
                t=row_text(d); 
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen.add(tok)
                y=row_label(d); 
                if y is not None: lbls[str(y)]+=1
                n+=1
        else:
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"path":str(fp), "error":f"{type(e).__name__}: {e}"}
    size = fp.stat().st_size if fp.exists() else 0
    return {"path":str(fp),"n":n,"labels":dict(lbls),"size_bytes":size,"sha256_head":sha256_head(fp) if size else None,"overlap": len(seen)/max(1,len(vocab))}

def rank_with(vec):
    # 拿最大 800 個大檔來測
    cands=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: continue
            if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]): continue
            cands.append(p)
        except Exception: 
            continue
    uniq=[]; seen=set()
    for p in sorted(cands, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, vec)
        if "error" in r: continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored[:30]

results={"top_intent": [], "top_spam": []}
if intent_vec is not None: results["top_intent"]=rank_with(intent_vec)
if spam_vec   is not None: results["top_spam"]=rank_with(spam_vec)

OUT = Path(os.environ["OUT"])
OUT.mkdir(parents=True, exist_ok=True)
(OUT/"FORENSICS.json").write_text(json.dumps({
    "models":{"intent":intent_meta,"spam":spam_meta},
    **results
}, ensure_ascii=False, indent=2), "utf-8")

def write_tsv(items, fp:Path):
    with fp.open("w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{(d[size_bytes] or 0)/1024/1024:.2f}\t{d[overlap]:.5f}\t{(d.get(sha256_head) or )[:16]}\n")

if results["top_intent"]: write_tsv(results["top_intent"], OUT/"TOP_INTENT.tsv")
if results["top_spam"]  : write_tsv(results["top_spam"],   OUT/"TOP_SPAM.tsv")

best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\n=== FORENSICS ===")
print("OUT   :", OUT)
print("JSON  :", OUT/"FORENSICS.json")
if best_intent: print("BEST intent:", best_intent)
if best_spam  : print("BEST spam  :", best_spam)
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
'
+ '[' -z '
set -Eeuo pipefail

# 鎖定模型（你指定的 SPAM；INTENT 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={r"\.git$", r"venv$", r"\.venv$", r"dist$", r"build$", r"node_modules$", r"artifacts($|_)", r"weights$", r"models$", r"reports_auto/logs$", r"__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir_name(name:str)->bool:
    for pat in IGNORE:
        if re.search(pat, name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dirnames[:]=[d for d in dirnames if want_dir_name(d)]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f: h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore") if fp.suffix.lower()==".gz" \
           else fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    keys=["text","content","body","message","email","subject","title","content_text"]
    if isinstance(d,dict):
        for k in keys:
            v=d.get(k)
            if isinstance(v,str) and v.strip(): return v
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    return d if isinstance(d,str) else ""

def row_label(d):
    if isinstance(d,dict):
        for k in ["label","y","target","class","category","is_spam","spam"]:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                return str(v)
    return None

def load_model(path):
    try:
        m=joblib.load(path); return m, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

def take_vectorizer(pipe):
    try:
        steps=[]
        if hasattr(pipe,"named_steps"): steps+=list(pipe.named_steps.items())
        if hasattr(pipe,"steps"): steps+=list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer": return st
    except Exception: pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind":None, "error":err, "classes":None, "vocab_size":None, "steps":[]}
    if m is None: return meta, None, None
    meta["kind"]=m.__class__.__name__
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL") or os.environ.get("INTENT_PKL_DEFAULT")
SPAM_PKL=os.environ.get("SPAM_PKL")

intent_meta=intent_model=intent_vec=None
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta=spam_model=spam_vec=None
if SPAM_PKL and Path(SPAM_PKL).exists():
    spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL)

print(json.dumps({"models":{"intent":intent_meta,"spam":spam_meta}}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    ana = vec.build_analyzer(); vocab=set(vec.vocabulary_.keys()); seen=set()
    n=0; lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try: d=json.loads(line)
                    except Exception: continue
                    t=row_text(d); 
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d); 
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else (dt.get("data", []) or [])
            for d in rows[:max_rows]:
                t=row_text(d); 
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen.add(tok)
                y=row_label(d); 
                if y is not None: lbls[str(y)]+=1
                n+=1
        else:
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"path":str(fp), "error":f"{type(e).__name__}: {e}"}
    size = fp.stat().st_size if fp.exists() else 0
    return {"path":str(fp),"n":n,"labels":dict(lbls),"size_bytes":size,"sha256_head":sha256_head(fp) if size else None,"overlap": len(seen)/max(1,len(vocab))}

def rank_with(vec):
    # 拿最大 800 個大檔來測
    cands=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: continue
            if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]): continue
            cands.append(p)
        except Exception: 
            continue
    uniq=[]; seen=set()
    for p in sorted(cands, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, vec)
        if "error" in r: continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored[:30]

results={"top_intent": [], "top_spam": []}
if intent_vec is not None: results["top_intent"]=rank_with(intent_vec)
if spam_vec   is not None: results["top_spam"]=rank_with(spam_vec)

OUT = Path(os.environ["OUT"])
OUT.mkdir(parents=True, exist_ok=True)
(OUT/"FORENSICS.json").write_text(json.dumps({
    "models":{"intent":intent_meta,"spam":spam_meta},
    **results
}, ensure_ascii=False, indent=2), "utf-8")

def write_tsv(items, fp:Path):
    with fp.open("w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{(d[size_bytes] or 0)/1024/1024:.2f}\t{d[overlap]:.5f}\t{(d.get(sha256_head) or )[:16]}\n")

if results["top_intent"]: write_tsv(results["top_intent"], OUT/"TOP_INTENT.tsv")
if results["top_spam"]  : write_tsv(results["top_spam"],   OUT/"TOP_SPAM.tsv")

best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\n=== FORENSICS ===")
print("OUT   :", OUT)
print("JSON  :", OUT/"FORENSICS.json")
if best_intent: print("BEST intent:", best_intent)
if best_spam  : print("BEST spam  :", best_spam)
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
' ']'
+ echo '== SNAPSHOT 20250920T153317 =='
+ pwd
+ uname -a
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT_PKL|SPAM_PKL|KIE_DIR|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc '
set -Eeuo pipefail

# 鎖定模型（你指定的 SPAM；INTENT 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={r"\.git$", r"venv$", r"\.venv$", r"dist$", r"build$", r"node_modules$", r"artifacts($|_)", r"weights$", r"models$", r"reports_auto/logs$", r"__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir_name(name:str)->bool:
    for pat in IGNORE:
        if re.search(pat, name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dirnames[:]=[d for d in dirnames if want_dir_name(d)]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f: h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore") if fp.suffix.lower()==".gz" \
           else fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    keys=["text","content","body","message","email","subject","title","content_text"]
    if isinstance(d,dict):
        for k in keys:
            v=d.get(k)
            if isinstance(v,str) and v.strip(): return v
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    return d if isinstance(d,str) else ""

def row_label(d):
    if isinstance(d,dict):
        for k in ["label","y","target","class","category","is_spam","spam"]:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                return str(v)
    return None

def load_model(path):
    try:
        m=joblib.load(path); return m, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

def take_vectorizer(pipe):
    try:
        steps=[]
        if hasattr(pipe,"named_steps"): steps+=list(pipe.named_steps.items())
        if hasattr(pipe,"steps"): steps+=list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer": return st
    except Exception: pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind":None, "error":err, "classes":None, "vocab_size":None, "steps":[]}
    if m is None: return meta, None, None
    meta["kind"]=m.__class__.__name__
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL") or os.environ.get("INTENT_PKL_DEFAULT")
SPAM_PKL=os.environ.get("SPAM_PKL")

intent_meta=intent_model=intent_vec=None
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta=spam_model=spam_vec=None
if SPAM_PKL and Path(SPAM_PKL).exists():
    spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL)

print(json.dumps({"models":{"intent":intent_meta,"spam":spam_meta}}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    ana = vec.build_analyzer(); vocab=set(vec.vocabulary_.keys()); seen=set()
    n=0; lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try: d=json.loads(line)
                    except Exception: continue
                    t=row_text(d); 
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d); 
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else (dt.get("data", []) or [])
            for d in rows[:max_rows]:
                t=row_text(d); 
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen.add(tok)
                y=row_label(d); 
                if y is not None: lbls[str(y)]+=1
                n+=1
        else:
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"path":str(fp), "error":f"{type(e).__name__}: {e}"}
    size = fp.stat().st_size if fp.exists() else 0
    return {"path":str(fp),"n":n,"labels":dict(lbls),"size_bytes":size,"sha256_head":sha256_head(fp) if size else None,"overlap": len(seen)/max(1,len(vocab))}

def rank_with(vec):
    # 拿最大 800 個大檔來測
    cands=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: continue
            if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]): continue
            cands.append(p)
        except Exception: 
            continue
    uniq=[]; seen=set()
    for p in sorted(cands, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, vec)
        if "error" in r: continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored[:30]

results={"top_intent": [], "top_spam": []}
if intent_vec is not None: results["top_intent"]=rank_with(intent_vec)
if spam_vec   is not None: results["top_spam"]=rank_with(spam_vec)

OUT = Path(os.environ["OUT"])
OUT.mkdir(parents=True, exist_ok=True)
(OUT/"FORENSICS.json").write_text(json.dumps({
    "models":{"intent":intent_meta,"spam":spam_meta},
    **results
}, ensure_ascii=False, indent=2), "utf-8")

def write_tsv(items, fp:Path):
    with fp.open("w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{(d[size_bytes] or 0)/1024/1024:.2f}\t{d[overlap]:.5f}\t{(d.get(sha256_head) or )[:16]}\n")

if results["top_intent"]: write_tsv(results["top_intent"], OUT/"TOP_INTENT.tsv")
if results["top_spam"]  : write_tsv(results["top_spam"],   OUT/"TOP_SPAM.tsv")

best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\n=== FORENSICS ===")
print("OUT   :", OUT)
print("JSON  :", OUT/"FORENSICS.json")
if best_intent: print("BEST intent:", best_intent)
if best_spam  : print("BEST spam  :", best_spam)
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
'
++ tee -a reports_auto/panic_20250920T153317/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : 
set -Eeuo pipefail

# 鎖定模型（你指定的 SPAM；INTENT 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={r"\.git$", r"venv$", r"\.venv$", r"dist$", r"build$", r"node_modules$", r"artifacts($|_)", r"weights$", r"models$", r"reports_auto/logs$", r"__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir_name(name:str)->bool:
    for pat in IGNORE:
        if re.search(pat, name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dirnames[:]=[d for d in dirnames if want_dir_name(d)]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f: h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore") if fp.suffix.lower()==".gz" \
           else fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    keys=["text","content","body","message","email","subject","title","content_text"]
    if isinstance(d,dict):
        for k in keys:
            v=d.get(k)
            if isinstance(v,str) and v.strip(): return v
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    return d if isinstance(d,str) else ""

def row_label(d):
    if isinstance(d,dict):
        for k in ["label","y","target","class","category","is_spam","spam"]:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                return str(v)
    return None

def load_model(path):
    try:
        m=joblib.load(path); return m, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

def take_vectorizer(pipe):
    try:
        steps=[]
        if hasattr(pipe,"named_steps"): steps+=list(pipe.named_steps.items())
        if hasattr(pipe,"steps"): steps+=list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer": return st
    except Exception: pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind":None, "error":err, "classes":None, "vocab_size":None, "steps":[]}
    if m is None: return meta, None, None
    meta["kind"]=m.__class__.__name__
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL") or os.environ.get("INTENT_PKL_DEFAULT")
SPAM_PKL=os.environ.get("SPAM_PKL")

intent_meta=intent_model=intent_vec=None
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta=spam_model=spam_vec=None
if SPAM_PKL and Path(SPAM_PKL).exists():
    spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL)

print(json.dumps({"models":{"intent":intent_meta,"spam":spam_meta}}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    ana = vec.build_analyzer(); vocab=set(vec.vocabulary_.keys()); seen=set()
    n=0; lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try: d=json.loads(line)
                    except Exception: continue
                    t=row_text(d); 
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d); 
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else (dt.get("data", []) or [])
            for d in rows[:max_rows]:
                t=row_text(d); 
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen.add(tok)
                y=row_label(d); 
                if y is not None: lbls[str(y)]+=1
                n+=1
        else:
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"path":str(fp), "error":f"{type(e).__name__}: {e}"}
    size = fp.stat().st_size if fp.exists() else 0
    return {"path":str(fp),"n":n,"labels":dict(lbls),"size_bytes":size,"sha256_head":sha256_head(fp) if size else None,"overlap": len(seen)/max(1,len(vocab))}

def rank_with(vec):
    # 拿最大 800 個大檔來測
    cands=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: continue
            if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]): continue
            cands.append(p)
        except Exception: 
            continue
    uniq=[]; seen=set()
    for p in sorted(cands, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, vec)
        if "error" in r: continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored[:30]

results={"top_intent": [], "top_spam": []}
if intent_vec is not None: results["top_intent"]=rank_with(intent_vec)
if spam_vec   is not None: results["top_spam"]=rank_with(spam_vec)

OUT = Path(os.environ["OUT"])
OUT.mkdir(parents=True, exist_ok=True)
(OUT/"FORENSICS.json").write_text(json.dumps({
    "models":{"intent":intent_meta,"spam":spam_meta},
    **results
}, ensure_ascii=False, indent=2), "utf-8")

def write_tsv(items, fp:Path):
    with fp.open("w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{(d[size_bytes] or 0)/1024/1024:.2f}\t{d[overlap]:.5f}\t{(d.get(sha256_head) or )[:16]}\n")

if results["top_intent"]: write_tsv(results["top_intent"], OUT/"TOP_INTENT.tsv")
if results["top_spam"]  : write_tsv(results["top_spam"],   OUT/"TOP_SPAM.tsv")

best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\n=== FORENSICS ===")
print("OUT   :", OUT)
print("JSON  :", OUT/"FORENSICS.json")
if best_intent: print("BEST intent:", best_intent)
if best_spam  : print("BEST spam  :", best_spam)
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
'
+ echo '- LOG  : reports_auto/panic_20250920T153317/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T153317/run.err'
+ echo '- PY   : reports_auto/panic_20250920T153317/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T153317/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T153317/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T153317/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T153317/run.err reports_auto/panic_20250920T153317/python_stderr.txt
+ grep -qi 'No module named '\''tools'\''' reports_auto/panic_20250920T153317/run.err reports_auto/panic_20250920T153317/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T153317/run.err reports_auto/panic_20250920T153317/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T153317/run.err reports_auto/panic_20250920T153317/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T153317/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ printf '%s\n' reports_auto/panic_20250920T153317/REPORT.md reports_auto/panic_20250920T153317/run.log reports_auto/panic_20250920T153317/run.err reports_auto/panic_20250920T153317/python_stderr.txt reports_auto/panic_20250920T153317/xtrace.sh reports_auto/panic_20250920T153317/system.txt reports_auto/panic_20250920T153317/oom.txt
+ echo
+ exit 1
