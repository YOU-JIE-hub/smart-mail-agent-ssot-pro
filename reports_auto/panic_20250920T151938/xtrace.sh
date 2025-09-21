+ CMD='
set -Eeuo pipefail

# 鎖定模型（你指定的 spam；intent 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={"\\.git$","venv$","\\.venv$","dist$","build$","node_modules$","artifacts$","artifacts_.*$","weights$","models$","reports_auto/logs$","__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir(p:Path)->bool:
    for pat in IGNORE:
        if re.search(pat, p.name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dp=Path(dirpath)
            # prune
            dirnames[:]=[d for d in dirnames if want_dir(Path(d))]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f:
        h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    if fp.suffix.lower()==".gz": 
        return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore")
    return fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    # 從常見欄位抓字串；不然就把所有 str 值拼起來
    keys = ["text","content","body","message","email","subject","title","content_text"]
    for k in keys:
        if isinstance(d,dict) and k in d and isinstance(d[k],str) and d[k].strip():
            return d[k]
    if isinstance(d,dict):
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    if isinstance(d,str): return d
    return ""

def row_label(d):
    keys = ["label","y","target","class","category","is_spam","spam"]
    if isinstance(d,dict):
        for k in keys:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                if isinstance(v,int): return str(v)
                if isinstance(v,str): return v
    return None

def load_model(path):
    try:
        m=joblib.load(path)
        return m, None
    except Exception as e:
        return None, str(e)

def take_vectorizer(pipe):
    # 在 pipeline 中找到 TfidfVectorizer
    try:
        steps = []
        if hasattr(pipe,"named_steps"):
            steps += list(pipe.named_steps.items())
        if hasattr(pipe,"steps"):
            steps += list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer":
                return st
    except Exception:
        pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind": None, "error": err, "classes": None, "vocab_size": None, "steps": []}
    if m is None:
        return meta, None, None
    meta["kind"]=m.__class__.__name__
    # 嘗試列出 steps
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    # classes_
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL", os.environ.get("INTENT_PKL_DEFAULT"))
SPAM_PKL=os.environ.get("SPAM_PKL")

outdir=Path("reports_auto")/f"forensics_{datetime.now().strftime("%Y%m%dT%H%M%S")}"
outdir.parent.mkdir(parents=True, exist_ok=True)
outdir.mkdir(parents=True, exist_ok=True)

intent_meta,intent_model,intent_vec = (None,None,None)
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL) if (SPAM_PKL and Path(SPAM_PKL).exists()) else (None,None,None)

models_info={"intent":intent_meta, "spam":spam_meta}
print(json.dumps({"ts":datetime.now().isoformat(timespec="seconds"),"models":models_info}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    # 用模型 analyzer 算資料檔詞彙重疊
    ana = vec.build_analyzer()
    vocab = set(vec.vocabulary_.keys())
    seen_tokens=set()
    n=0
    lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        d=json.loads(line)
                    except Exception:
                        continue
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t): 
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else dt.get("data", [])
            for d in rows[:max_rows]:
                t=row_text(d)
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen_tokens.add(tok)
                y=row_label(d)
                if y is not None: lbls[str(y)]+=1
                n+=1
        else: # csv/tsv
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"error": str(e)}
    return {
        "path": str(fp),
        "n": n,
        "labels": dict(lbls),
        "size_bytes": fp.stat().st_size if fp.exists() else None,
        "sha256_head": sha256_head(fp) if fp.exists() else None,
        "overlap": len(seen_tokens)/max(1,len(vec.vocabulary_))
    }

def rank_for(model_vec):
    files=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: 
                continue
        except Exception:
            continue
        if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]):
            continue
        files.append(p)
    # 去重 & 限制數量
    uniq=[]
    seen=set()
    for p in sorted(files, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, model_vec)
        if "error" in r: 
            continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored

results={"models":models_info, "top_intent":[], "top_spam":[]}
if intent_vec is not None:
    results["top_intent"]=rank_for(intent_vec)[:30]
if spam_vec is not None:
    results["top_spam"]=rank_for(spam_vec)[:30]

# 輸出
OUT=Path("${OUT}")
(OUT).mkdir(parents=True, exist_ok=True)
with (OUT/"FORENSICS.json").open("w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

def write_tsv(items, fp):
    import math
    with open(fp, "w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            sz = (d["size_bytes"] or 0)/1024/1024
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{sz:.2f}\t{d[overlap]:.5f}\t{(d[sha256_head] or )[:16]}\n")

if results["top_intent"]:
    write_tsv(results["top_intent"], str(OUT/"TOP_INTENT.tsv"))
if results["top_spam"]:
    write_tsv(results["top_spam"], str(OUT/"TOP_SPAM.tsv"))

# 回顯最佳猜測
best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\\n=== FORENSICS ===")
print(f"OUT   : {OUT}")
print(f"JSON  : {OUT/FORENSICS.json}")
if results["top_intent"]: print(f"BEST intent: {best_intent}")
if results["top_spam"]  : print(f"BEST spam  : {best_spam}")
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
'
+ '[' -z '
set -Eeuo pipefail

# 鎖定模型（你指定的 spam；intent 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={"\\.git$","venv$","\\.venv$","dist$","build$","node_modules$","artifacts$","artifacts_.*$","weights$","models$","reports_auto/logs$","__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir(p:Path)->bool:
    for pat in IGNORE:
        if re.search(pat, p.name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dp=Path(dirpath)
            # prune
            dirnames[:]=[d for d in dirnames if want_dir(Path(d))]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f:
        h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    if fp.suffix.lower()==".gz": 
        return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore")
    return fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    # 從常見欄位抓字串；不然就把所有 str 值拼起來
    keys = ["text","content","body","message","email","subject","title","content_text"]
    for k in keys:
        if isinstance(d,dict) and k in d and isinstance(d[k],str) and d[k].strip():
            return d[k]
    if isinstance(d,dict):
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    if isinstance(d,str): return d
    return ""

def row_label(d):
    keys = ["label","y","target","class","category","is_spam","spam"]
    if isinstance(d,dict):
        for k in keys:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                if isinstance(v,int): return str(v)
                if isinstance(v,str): return v
    return None

def load_model(path):
    try:
        m=joblib.load(path)
        return m, None
    except Exception as e:
        return None, str(e)

def take_vectorizer(pipe):
    # 在 pipeline 中找到 TfidfVectorizer
    try:
        steps = []
        if hasattr(pipe,"named_steps"):
            steps += list(pipe.named_steps.items())
        if hasattr(pipe,"steps"):
            steps += list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer":
                return st
    except Exception:
        pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind": None, "error": err, "classes": None, "vocab_size": None, "steps": []}
    if m is None:
        return meta, None, None
    meta["kind"]=m.__class__.__name__
    # 嘗試列出 steps
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    # classes_
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL", os.environ.get("INTENT_PKL_DEFAULT"))
SPAM_PKL=os.environ.get("SPAM_PKL")

outdir=Path("reports_auto")/f"forensics_{datetime.now().strftime("%Y%m%dT%H%M%S")}"
outdir.parent.mkdir(parents=True, exist_ok=True)
outdir.mkdir(parents=True, exist_ok=True)

intent_meta,intent_model,intent_vec = (None,None,None)
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL) if (SPAM_PKL and Path(SPAM_PKL).exists()) else (None,None,None)

models_info={"intent":intent_meta, "spam":spam_meta}
print(json.dumps({"ts":datetime.now().isoformat(timespec="seconds"),"models":models_info}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    # 用模型 analyzer 算資料檔詞彙重疊
    ana = vec.build_analyzer()
    vocab = set(vec.vocabulary_.keys())
    seen_tokens=set()
    n=0
    lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        d=json.loads(line)
                    except Exception:
                        continue
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t): 
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else dt.get("data", [])
            for d in rows[:max_rows]:
                t=row_text(d)
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen_tokens.add(tok)
                y=row_label(d)
                if y is not None: lbls[str(y)]+=1
                n+=1
        else: # csv/tsv
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"error": str(e)}
    return {
        "path": str(fp),
        "n": n,
        "labels": dict(lbls),
        "size_bytes": fp.stat().st_size if fp.exists() else None,
        "sha256_head": sha256_head(fp) if fp.exists() else None,
        "overlap": len(seen_tokens)/max(1,len(vec.vocabulary_))
    }

def rank_for(model_vec):
    files=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: 
                continue
        except Exception:
            continue
        if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]):
            continue
        files.append(p)
    # 去重 & 限制數量
    uniq=[]
    seen=set()
    for p in sorted(files, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, model_vec)
        if "error" in r: 
            continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored

results={"models":models_info, "top_intent":[], "top_spam":[]}
if intent_vec is not None:
    results["top_intent"]=rank_for(intent_vec)[:30]
if spam_vec is not None:
    results["top_spam"]=rank_for(spam_vec)[:30]

# 輸出
OUT=Path("${OUT}")
(OUT).mkdir(parents=True, exist_ok=True)
with (OUT/"FORENSICS.json").open("w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

def write_tsv(items, fp):
    import math
    with open(fp, "w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            sz = (d["size_bytes"] or 0)/1024/1024
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{sz:.2f}\t{d[overlap]:.5f}\t{(d[sha256_head] or )[:16]}\n")

if results["top_intent"]:
    write_tsv(results["top_intent"], str(OUT/"TOP_INTENT.tsv"))
if results["top_spam"]:
    write_tsv(results["top_spam"], str(OUT/"TOP_SPAM.tsv"))

# 回顯最佳猜測
best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\\n=== FORENSICS ===")
print(f"OUT   : {OUT}")
print(f"JSON  : {OUT/FORENSICS.json}")
if results["top_intent"]: print(f"BEST intent: {best_intent}")
if results["top_spam"]  : print(f"BEST spam  : {best_spam}")
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
' ']'
+ echo '== SNAPSHOT 20250920T151938 =='
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

# 鎖定模型（你指定的 spam；intent 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={"\\.git$","venv$","\\.venv$","dist$","build$","node_modules$","artifacts$","artifacts_.*$","weights$","models$","reports_auto/logs$","__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir(p:Path)->bool:
    for pat in IGNORE:
        if re.search(pat, p.name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dp=Path(dirpath)
            # prune
            dirnames[:]=[d for d in dirnames if want_dir(Path(d))]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f:
        h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    if fp.suffix.lower()==".gz": 
        return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore")
    return fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    # 從常見欄位抓字串；不然就把所有 str 值拼起來
    keys = ["text","content","body","message","email","subject","title","content_text"]
    for k in keys:
        if isinstance(d,dict) and k in d and isinstance(d[k],str) and d[k].strip():
            return d[k]
    if isinstance(d,dict):
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    if isinstance(d,str): return d
    return ""

def row_label(d):
    keys = ["label","y","target","class","category","is_spam","spam"]
    if isinstance(d,dict):
        for k in keys:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                if isinstance(v,int): return str(v)
                if isinstance(v,str): return v
    return None

def load_model(path):
    try:
        m=joblib.load(path)
        return m, None
    except Exception as e:
        return None, str(e)

def take_vectorizer(pipe):
    # 在 pipeline 中找到 TfidfVectorizer
    try:
        steps = []
        if hasattr(pipe,"named_steps"):
            steps += list(pipe.named_steps.items())
        if hasattr(pipe,"steps"):
            steps += list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer":
                return st
    except Exception:
        pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind": None, "error": err, "classes": None, "vocab_size": None, "steps": []}
    if m is None:
        return meta, None, None
    meta["kind"]=m.__class__.__name__
    # 嘗試列出 steps
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    # classes_
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL", os.environ.get("INTENT_PKL_DEFAULT"))
SPAM_PKL=os.environ.get("SPAM_PKL")

outdir=Path("reports_auto")/f"forensics_{datetime.now().strftime("%Y%m%dT%H%M%S")}"
outdir.parent.mkdir(parents=True, exist_ok=True)
outdir.mkdir(parents=True, exist_ok=True)

intent_meta,intent_model,intent_vec = (None,None,None)
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL) if (SPAM_PKL and Path(SPAM_PKL).exists()) else (None,None,None)

models_info={"intent":intent_meta, "spam":spam_meta}
print(json.dumps({"ts":datetime.now().isoformat(timespec="seconds"),"models":models_info}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    # 用模型 analyzer 算資料檔詞彙重疊
    ana = vec.build_analyzer()
    vocab = set(vec.vocabulary_.keys())
    seen_tokens=set()
    n=0
    lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        d=json.loads(line)
                    except Exception:
                        continue
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t): 
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else dt.get("data", [])
            for d in rows[:max_rows]:
                t=row_text(d)
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen_tokens.add(tok)
                y=row_label(d)
                if y is not None: lbls[str(y)]+=1
                n+=1
        else: # csv/tsv
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"error": str(e)}
    return {
        "path": str(fp),
        "n": n,
        "labels": dict(lbls),
        "size_bytes": fp.stat().st_size if fp.exists() else None,
        "sha256_head": sha256_head(fp) if fp.exists() else None,
        "overlap": len(seen_tokens)/max(1,len(vec.vocabulary_))
    }

def rank_for(model_vec):
    files=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: 
                continue
        except Exception:
            continue
        if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]):
            continue
        files.append(p)
    # 去重 & 限制數量
    uniq=[]
    seen=set()
    for p in sorted(files, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, model_vec)
        if "error" in r: 
            continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored

results={"models":models_info, "top_intent":[], "top_spam":[]}
if intent_vec is not None:
    results["top_intent"]=rank_for(intent_vec)[:30]
if spam_vec is not None:
    results["top_spam"]=rank_for(spam_vec)[:30]

# 輸出
OUT=Path("${OUT}")
(OUT).mkdir(parents=True, exist_ok=True)
with (OUT/"FORENSICS.json").open("w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

def write_tsv(items, fp):
    import math
    with open(fp, "w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            sz = (d["size_bytes"] or 0)/1024/1024
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{sz:.2f}\t{d[overlap]:.5f}\t{(d[sha256_head] or )[:16]}\n")

if results["top_intent"]:
    write_tsv(results["top_intent"], str(OUT/"TOP_INTENT.tsv"))
if results["top_spam"]:
    write_tsv(results["top_spam"], str(OUT/"TOP_SPAM.tsv"))

# 回顯最佳猜測
best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\\n=== FORENSICS ===")
print(f"OUT   : {OUT}")
print(f"JSON  : {OUT/FORENSICS.json}")
if results["top_intent"]: print(f"BEST intent: {best_intent}")
if results["top_spam"]  : print(f"BEST spam  : {best_spam}")
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
'
++ tee -a reports_auto/panic_20250920T151938/python_stderr.txt
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

# 鎖定模型（你指定的 spam；intent 盡量用現有 pkl）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL_DEFAULT="models/intent/artifacts/model_pipeline.pkl"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"

python3 - <<PY
import os, re, json, csv, gzip, io, hashlib, sys
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import joblib

ROOTS=[
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]
IGNORE={"\\.git$","venv$","\\.venv$","dist$","build$","node_modules$","artifacts$","artifacts_.*$","weights$","models$","reports_auto/logs$","__pycache__$"}
DATA_EXT={".jsonl",".json",".csv",".tsv"}

def want_dir(p:Path)->bool:
    for pat in IGNORE:
        if re.search(pat, p.name): return False
    return True

def walk_files(roots):
    for r in roots:
        r=Path(r)
        for dirpath, dirnames, filenames in os.walk(r):
            dp=Path(dirpath)
            # prune
            dirnames[:]=[d for d in dirnames if want_dir(Path(d))]
            for f in filenames:
                if Path(f).suffix.lower() in DATA_EXT:
                    yield Path(dirpath)/f

def sha256_head(fp:Path, nbytes=2_000_000):
    h=hashlib.sha256()
    with fp.open("rb") as f:
        h.update(f.read(nbytes))
    return h.hexdigest()

def safe_open(fp:Path):
    if fp.suffix.lower()==".gz": 
        return io.TextIOWrapper(gzip.open(fp,"rb"), encoding="utf-8", errors="ignore")
    return fp.open("r", encoding="utf-8", errors="ignore")

def row_text(d):
    # 從常見欄位抓字串；不然就把所有 str 值拼起來
    keys = ["text","content","body","message","email","subject","title","content_text"]
    for k in keys:
        if isinstance(d,dict) and k in d and isinstance(d[k],str) and d[k].strip():
            return d[k]
    if isinstance(d,dict):
        parts=[str(v) for v in d.values() if isinstance(v,str) and v.strip()]
        if parts: return " ".join(parts)
    if isinstance(d,str): return d
    return ""

def row_label(d):
    keys = ["label","y","target","class","category","is_spam","spam"]
    if isinstance(d,dict):
        for k in keys:
            if k in d:
                v=d[k]
                if isinstance(v,bool): return "spam" if v else "ham"
                if isinstance(v,int): return str(v)
                if isinstance(v,str): return v
    return None

def load_model(path):
    try:
        m=joblib.load(path)
        return m, None
    except Exception as e:
        return None, str(e)

def take_vectorizer(pipe):
    # 在 pipeline 中找到 TfidfVectorizer
    try:
        steps = []
        if hasattr(pipe,"named_steps"):
            steps += list(pipe.named_steps.items())
        if hasattr(pipe,"steps"):
            steps += list(pipe.steps)
        for name, st in steps:
            if st.__class__.__name__=="TfidfVectorizer":
                return st
    except Exception:
        pass
    return None

def model_meta(path):
    m, err = load_model(path)
    meta={"path":path, "kind": None, "error": err, "classes": None, "vocab_size": None, "steps": []}
    if m is None:
        return meta, None, None
    meta["kind"]=m.__class__.__name__
    # 嘗試列出 steps
    try:
        if hasattr(m,"steps"): meta["steps"]=[n for n,_ in m.steps]
        elif hasattr(m,"named_steps"): meta["steps"]=list(m.named_steps.keys())
    except Exception: pass
    # classes_
    for obj in [m, getattr(m,"_final_estimator",None), getattr(m,"final_estimator_",None)]:
        if obj is not None and hasattr(obj,"classes_"):
            try: meta["classes"]=list(obj.classes_)
            except Exception: pass
    vec = take_vectorizer(m)
    if vec is not None and hasattr(vec,"vocabulary_"):
        meta["vocab_size"]=len(vec.vocabulary_)
    return meta, m, vec

INTENT_PKL=os.environ.get("INTENT_PKL", os.environ.get("INTENT_PKL_DEFAULT"))
SPAM_PKL=os.environ.get("SPAM_PKL")

outdir=Path("reports_auto")/f"forensics_{datetime.now().strftime("%Y%m%dT%H%M%S")}"
outdir.parent.mkdir(parents=True, exist_ok=True)
outdir.mkdir(parents=True, exist_ok=True)

intent_meta,intent_model,intent_vec = (None,None,None)
if INTENT_PKL and Path(INTENT_PKL).exists():
    intent_meta,intent_model,intent_vec = model_meta(INTENT_PKL)
spam_meta,spam_model,spam_vec = model_meta(SPAM_PKL) if (SPAM_PKL and Path(SPAM_PKL).exists()) else (None,None,None)

models_info={"intent":intent_meta, "spam":spam_meta}
print(json.dumps({"ts":datetime.now().isoformat(timespec="seconds"),"models":models_info}, ensure_ascii=False, indent=2))

def score_file(fp:Path, vec, max_rows=4000):
    # 用模型 analyzer 算資料檔詞彙重疊
    ana = vec.build_analyzer()
    vocab = set(vec.vocabulary_.keys())
    seen_tokens=set()
    n=0
    lbls=Counter()
    try:
        if fp.suffix.lower()==".jsonl":
            with safe_open(fp) as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        d=json.loads(line)
                    except Exception:
                        continue
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t): 
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
        elif fp.suffix.lower()==".json":
            with safe_open(fp) as f:
                dt=json.load(f)
            rows = dt if isinstance(dt,list) else dt.get("data", [])
            for d in rows[:max_rows]:
                t=row_text(d)
                if not t: continue
                for tok in ana(t):
                    if tok in vocab: seen_tokens.add(tok)
                y=row_label(d)
                if y is not None: lbls[str(y)]+=1
                n+=1
        else: # csv/tsv
            delim = "\t" if fp.suffix.lower()==".tsv" else ","
            with safe_open(fp) as f:
                rdr = csv.DictReader(f, delimiter=delim)
                for d in rdr:
                    t=row_text(d)
                    if not t: continue
                    for tok in ana(t):
                        if tok in vocab: seen_tokens.add(tok)
                    y=row_label(d)
                    if y is not None: lbls[str(y)]+=1
                    n+=1
                    if n>=max_rows: break
    except Exception as e:
        return {"error": str(e)}
    return {
        "path": str(fp),
        "n": n,
        "labels": dict(lbls),
        "size_bytes": fp.stat().st_size if fp.exists() else None,
        "sha256_head": sha256_head(fp) if fp.exists() else None,
        "overlap": len(seen_tokens)/max(1,len(vec.vocabulary_))
    }

def rank_for(model_vec):
    files=[]
    for p in walk_files(ROOTS):
        try:
            if p.stat().st_size<10_000: 
                continue
        except Exception:
            continue
        if any(seg in p.as_posix() for seg in ["/artifacts_","/models/","/reports_auto/logs/"]):
            continue
        files.append(p)
    # 去重 & 限制數量
    uniq=[]
    seen=set()
    for p in sorted(files, key=lambda x: (-x.stat().st_size, x.as_posix()))[:800]:
        k=(p.name, p.stat().st_size)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    scored=[]
    for p in uniq:
        r=score_file(p, model_vec)
        if "error" in r: 
            continue
        scored.append(r)
    scored.sort(key=lambda d: (-d["overlap"], -d["n"], -d["size_bytes"]))
    return scored

results={"models":models_info, "top_intent":[], "top_spam":[]}
if intent_vec is not None:
    results["top_intent"]=rank_for(intent_vec)[:30]
if spam_vec is not None:
    results["top_spam"]=rank_for(spam_vec)[:30]

# 輸出
OUT=Path("${OUT}")
(OUT).mkdir(parents=True, exist_ok=True)
with (OUT/"FORENSICS.json").open("w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

def write_tsv(items, fp):
    import math
    with open(fp, "w", encoding="utf-8") as f:
        f.write("rank\tpath\tn\tlabels\tsize_mb\toverlap\tsha256_head\n")
        for i,d in enumerate(items,1):
            sz = (d["size_bytes"] or 0)/1024/1024
            f.write(f"{i}\t{d[path]}\t{d[n]}\t{json.dumps(d[labels],ensure_ascii=False)}\t{sz:.2f}\t{d[overlap]:.5f}\t{(d[sha256_head] or )[:16]}\n")

if results["top_intent"]:
    write_tsv(results["top_intent"], str(OUT/"TOP_INTENT.tsv"))
if results["top_spam"]:
    write_tsv(results["top_spam"], str(OUT/"TOP_SPAM.tsv"))

# 回顯最佳猜測
best_intent = results["top_intent"][0]["path"] if results["top_intent"] else None
best_spam   = results["top_spam"][0]["path"]   if results["top_spam"]   else None
print("\\n=== FORENSICS ===")
print(f"OUT   : {OUT}")
print(f"JSON  : {OUT/FORENSICS.json}")
if results["top_intent"]: print(f"BEST intent: {best_intent}")
if results["top_spam"]  : print(f"BEST spam  : {best_spam}")
PY

echo
echo "[NEXT] 檢視結果摘要"
LATEST="$(ls -1dt reports_auto/forensics_* | head -1)"
echo "[forensics] \$LATEST=\$LATEST"
[ -n "$LATEST" ] && { head -n 30 "$LATEST/FORENSICS.json" || true; echo; sed -n "1,40p" "$LATEST/TOP_INTENT.tsv" 2>/dev/null || true; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv" 2>/dev/null || true; }
'
+ echo '- LOG  : reports_auto/panic_20250920T151938/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T151938/run.err'
+ echo '- PY   : reports_auto/panic_20250920T151938/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T151938/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T151938/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T151938/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T151938/run.err reports_auto/panic_20250920T151938/python_stderr.txt
+ grep -qi 'No module named '\''tools'\''' reports_auto/panic_20250920T151938/run.err reports_auto/panic_20250920T151938/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T151938/run.err reports_auto/panic_20250920T151938/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T151938/run.err reports_auto/panic_20250920T151938/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T151938/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ printf '%s\n' reports_auto/panic_20250920T151938/REPORT.md reports_auto/panic_20250920T151938/run.log reports_auto/panic_20250920T151938/run.err reports_auto/panic_20250920T151938/python_stderr.txt reports_auto/panic_20250920T151938/xtrace.sh reports_auto/panic_20250920T151938/system.txt reports_auto/panic_20250920T151938/oom.txt
+ echo
+ exit 1
