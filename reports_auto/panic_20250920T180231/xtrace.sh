+ CMD='
set -Eeuo pipefail
cd ~/projects/smart-mail-agent-ssot-pro

# 鎖定：你指定的 SPAM 模型；INTENT 用現有 pkl（缺就只跑 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

# 寫一次性 Python 到這次 OUT（不動你的 repo）
cat > "$OUT/forensics.py" << "PY"
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

# ---------- utils ----------
def _json_sanitize(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer, np.floating, np.bool_)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return sorted(list(o))
    if isinstance(o, Counter): return dict(o)
    if isinstance(o, Path): return str(o)
    return o

def jd(x): return json.dumps(x, ensure_ascii=False, indent=2, default=_json_sanitize)

token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")
def toks(s:str): return token_re.findall(s.lower())

def load_pipe_meta(pkl_path):
    meta = {"path": pkl_path, "ok": False}
    if not pkl_path or not Path(pkl_path).exists():
        meta["error"] = "missing"
        return set(), meta
    try:
        pipe = joblib.load(pkl_path)
        steps = dict(getattr(pipe, "named_steps", {}))
        vec = steps.get("tfidf") or steps.get("tfidfvectorizer")
        clf = steps.get("lr") or steps.get("logreg") or steps.get("calibratedclassifiercv")
        vocab = set(vec.vocabulary_.keys()) if vec is not None else set()
        classes = list(getattr(clf, "classes_", [])) if clf is not None else []
        meta.update(ok=True, steps=list(steps.keys()), vocab_size=len(vocab), classes=classes)
        return vocab, meta
    except Exception as e:
        meta["error"] = repr(e)
        return set(), meta

def sample_lines(p: Path, limit=4000, bytes_cap=40_000_000):
    try:
        size = p.stat().st_size
        if size > bytes_cap:
            data = p.open("rb").read(20_000_000).decode("utf-8","ignore").splitlines()
        else:
            data = p.read_text("utf-8","ignore").splitlines()
        n = 0
        for ln in data:
            ln = ln.strip()
            if not ln: continue
            yield ln
            n += 1
            if n >= limit: break
    except Exception:
        return

def iter_texts(p: Path, limit=4000):
    n = 0
    for ln in sample_lines(p, limit=limit):
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message","msg"):
                    v = obj.get(k)
                    if isinstance(v,str) and v.strip():
                        yield v; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit: break

def label_dist(p: Path):
    d = Counter()
    for ln in sample_lines(p, limit=6000):
        if not ln.startswith("{"): continue
        try:
            obj = json.loads(ln)
            for k in ("label","labels","y","target","intent","category"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v, (str,int)): d[str(v)] += 1
                    break
        except Exception:
            pass
    return dict(d.most_common(12))

def overlap_score(p: Path, vocab: set[str]):
    if not vocab: return 0.0, 0, {}
    seen = Counter(); n = 0
    for t in iter_texts(p, limit=4000):
        n += 1
        for tk in toks(t):
            if tk in vocab: seen[tk] += 1
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(25))

# ---------- main ----------
OUT = Path(os.environ.get("OUT") or "reports_auto/forensics_fallback")
OUT.mkdir(parents=True, exist_ok=True)

spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

v_spam,   m_spam = load_pipe_meta(spam_pkl)
v_intent, m_int  = load_pipe_meta(intent_pkl)

roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

# 候選集（先放你最可能用到的）
cands = [
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]

# 再掃描（僅 *.jsonl、檔名含 dataset/train/spamassassin；排除 reports_auto/logs）
def under_logs(p: Path) -> bool:
    s = p.as_posix()
    return "/reports_auto/logs/" in s or s.endswith("/reports_auto/logs")

for r in roots:
    if not r.exists(): continue
    for pp in r.rglob("*.jsonl"):
        name = pp.name.lower()
        if (("dataset" in name) or ("train" in name) or ("spamassassin" in name)) and not under_logs(pp):
            cands.append(str(pp))

# 去重
cands = [str(Path(p)) for p in dict.fromkeys(cands)]

rank_intent, rank_spam = [], []
details = {}
for p in cands:
    P = Path(p)
    if not P.exists(): continue
    try:
        s_i, n_i, _ = overlap_score(P, v_intent) if v_intent else (0.0,0,{})
        s_s, n_s, _ = overlap_score(P, v_spam)
        L = label_dist(P)
        entry = {
            "path": str(P),
            "n": int(max(n_i,n_s)),
            "labels": L,
            "size_mb": round(P.stat().st_size/1_000_000, 2)
        }
        rank_intent.append((float(s_i), entry))
        rank_spam.append((float(s_s), entry))
        details[str(P)] = entry
    except Exception as e:
        details[str(P)] = {"path": str(P), "error": repr(e)}

rank_intent.sort(key=lambda x: x[0], reverse=True)
rank_spam.sort(key=lambda x: x[0], reverse=True)

best_intent = (rank_intent[0][1] if rank_intent else None)
best_spam   = (rank_spam[0][1]   if rank_spam   else None)

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:50]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:50]],
    "picked": {"intent": best_intent, "spam": best_spam}
}

(OUT/"FORENSICS.json").write_text(jd(summary), "utf-8")

with open(OUT/"TOP_INTENT.tsv","w",encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_intent[:50],1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")

with open(OUT/"TOP_SPAM.tsv","w",encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_spam[:50],1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")

print(jd({"OUT": str(OUT), "BEST": {"intent": best_intent, "spam": best_spam}}))
PY

python3 "$OUT/forensics.py"
'
+ '[' -z '
set -Eeuo pipefail
cd ~/projects/smart-mail-agent-ssot-pro

# 鎖定：你指定的 SPAM 模型；INTENT 用現有 pkl（缺就只跑 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

# 寫一次性 Python 到這次 OUT（不動你的 repo）
cat > "$OUT/forensics.py" << "PY"
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

# ---------- utils ----------
def _json_sanitize(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer, np.floating, np.bool_)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return sorted(list(o))
    if isinstance(o, Counter): return dict(o)
    if isinstance(o, Path): return str(o)
    return o

def jd(x): return json.dumps(x, ensure_ascii=False, indent=2, default=_json_sanitize)

token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")
def toks(s:str): return token_re.findall(s.lower())

def load_pipe_meta(pkl_path):
    meta = {"path": pkl_path, "ok": False}
    if not pkl_path or not Path(pkl_path).exists():
        meta["error"] = "missing"
        return set(), meta
    try:
        pipe = joblib.load(pkl_path)
        steps = dict(getattr(pipe, "named_steps", {}))
        vec = steps.get("tfidf") or steps.get("tfidfvectorizer")
        clf = steps.get("lr") or steps.get("logreg") or steps.get("calibratedclassifiercv")
        vocab = set(vec.vocabulary_.keys()) if vec is not None else set()
        classes = list(getattr(clf, "classes_", [])) if clf is not None else []
        meta.update(ok=True, steps=list(steps.keys()), vocab_size=len(vocab), classes=classes)
        return vocab, meta
    except Exception as e:
        meta["error"] = repr(e)
        return set(), meta

def sample_lines(p: Path, limit=4000, bytes_cap=40_000_000):
    try:
        size = p.stat().st_size
        if size > bytes_cap:
            data = p.open("rb").read(20_000_000).decode("utf-8","ignore").splitlines()
        else:
            data = p.read_text("utf-8","ignore").splitlines()
        n = 0
        for ln in data:
            ln = ln.strip()
            if not ln: continue
            yield ln
            n += 1
            if n >= limit: break
    except Exception:
        return

def iter_texts(p: Path, limit=4000):
    n = 0
    for ln in sample_lines(p, limit=limit):
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message","msg"):
                    v = obj.get(k)
                    if isinstance(v,str) and v.strip():
                        yield v; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit: break

def label_dist(p: Path):
    d = Counter()
    for ln in sample_lines(p, limit=6000):
        if not ln.startswith("{"): continue
        try:
            obj = json.loads(ln)
            for k in ("label","labels","y","target","intent","category"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v, (str,int)): d[str(v)] += 1
                    break
        except Exception:
            pass
    return dict(d.most_common(12))

def overlap_score(p: Path, vocab: set[str]):
    if not vocab: return 0.0, 0, {}
    seen = Counter(); n = 0
    for t in iter_texts(p, limit=4000):
        n += 1
        for tk in toks(t):
            if tk in vocab: seen[tk] += 1
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(25))

# ---------- main ----------
OUT = Path(os.environ.get("OUT") or "reports_auto/forensics_fallback")
OUT.mkdir(parents=True, exist_ok=True)

spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

v_spam,   m_spam = load_pipe_meta(spam_pkl)
v_intent, m_int  = load_pipe_meta(intent_pkl)

roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

# 候選集（先放你最可能用到的）
cands = [
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]

# 再掃描（僅 *.jsonl、檔名含 dataset/train/spamassassin；排除 reports_auto/logs）
def under_logs(p: Path) -> bool:
    s = p.as_posix()
    return "/reports_auto/logs/" in s or s.endswith("/reports_auto/logs")

for r in roots:
    if not r.exists(): continue
    for pp in r.rglob("*.jsonl"):
        name = pp.name.lower()
        if (("dataset" in name) or ("train" in name) or ("spamassassin" in name)) and not under_logs(pp):
            cands.append(str(pp))

# 去重
cands = [str(Path(p)) for p in dict.fromkeys(cands)]

rank_intent, rank_spam = [], []
details = {}
for p in cands:
    P = Path(p)
    if not P.exists(): continue
    try:
        s_i, n_i, _ = overlap_score(P, v_intent) if v_intent else (0.0,0,{})
        s_s, n_s, _ = overlap_score(P, v_spam)
        L = label_dist(P)
        entry = {
            "path": str(P),
            "n": int(max(n_i,n_s)),
            "labels": L,
            "size_mb": round(P.stat().st_size/1_000_000, 2)
        }
        rank_intent.append((float(s_i), entry))
        rank_spam.append((float(s_s), entry))
        details[str(P)] = entry
    except Exception as e:
        details[str(P)] = {"path": str(P), "error": repr(e)}

rank_intent.sort(key=lambda x: x[0], reverse=True)
rank_spam.sort(key=lambda x: x[0], reverse=True)

best_intent = (rank_intent[0][1] if rank_intent else None)
best_spam   = (rank_spam[0][1]   if rank_spam   else None)

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:50]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:50]],
    "picked": {"intent": best_intent, "spam": best_spam}
}

(OUT/"FORENSICS.json").write_text(jd(summary), "utf-8")

with open(OUT/"TOP_INTENT.tsv","w",encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_intent[:50],1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")

with open(OUT/"TOP_SPAM.tsv","w",encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_spam[:50],1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")

print(jd({"OUT": str(OUT), "BEST": {"intent": best_intent, "spam": best_spam}}))
PY

python3 "$OUT/forensics.py"
' ']'
+ echo '== SNAPSHOT 20250920T180231 =='
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
cd ~/projects/smart-mail-agent-ssot-pro

# 鎖定：你指定的 SPAM 模型；INTENT 用現有 pkl（缺就只跑 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

# 寫一次性 Python 到這次 OUT（不動你的 repo）
cat > "$OUT/forensics.py" << "PY"
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

# ---------- utils ----------
def _json_sanitize(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer, np.floating, np.bool_)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return sorted(list(o))
    if isinstance(o, Counter): return dict(o)
    if isinstance(o, Path): return str(o)
    return o

def jd(x): return json.dumps(x, ensure_ascii=False, indent=2, default=_json_sanitize)

token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")
def toks(s:str): return token_re.findall(s.lower())

def load_pipe_meta(pkl_path):
    meta = {"path": pkl_path, "ok": False}
    if not pkl_path or not Path(pkl_path).exists():
        meta["error"] = "missing"
        return set(), meta
    try:
        pipe = joblib.load(pkl_path)
        steps = dict(getattr(pipe, "named_steps", {}))
        vec = steps.get("tfidf") or steps.get("tfidfvectorizer")
        clf = steps.get("lr") or steps.get("logreg") or steps.get("calibratedclassifiercv")
        vocab = set(vec.vocabulary_.keys()) if vec is not None else set()
        classes = list(getattr(clf, "classes_", [])) if clf is not None else []
        meta.update(ok=True, steps=list(steps.keys()), vocab_size=len(vocab), classes=classes)
        return vocab, meta
    except Exception as e:
        meta["error"] = repr(e)
        return set(), meta

def sample_lines(p: Path, limit=4000, bytes_cap=40_000_000):
    try:
        size = p.stat().st_size
        if size > bytes_cap:
            data = p.open("rb").read(20_000_000).decode("utf-8","ignore").splitlines()
        else:
            data = p.read_text("utf-8","ignore").splitlines()
        n = 0
        for ln in data:
            ln = ln.strip()
            if not ln: continue
            yield ln
            n += 1
            if n >= limit: break
    except Exception:
        return

def iter_texts(p: Path, limit=4000):
    n = 0
    for ln in sample_lines(p, limit=limit):
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message","msg"):
                    v = obj.get(k)
                    if isinstance(v,str) and v.strip():
                        yield v; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit: break

def label_dist(p: Path):
    d = Counter()
    for ln in sample_lines(p, limit=6000):
        if not ln.startswith("{"): continue
        try:
            obj = json.loads(ln)
            for k in ("label","labels","y","target","intent","category"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v, (str,int)): d[str(v)] += 1
                    break
        except Exception:
            pass
    return dict(d.most_common(12))

def overlap_score(p: Path, vocab: set[str]):
    if not vocab: return 0.0, 0, {}
    seen = Counter(); n = 0
    for t in iter_texts(p, limit=4000):
        n += 1
        for tk in toks(t):
            if tk in vocab: seen[tk] += 1
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(25))

# ---------- main ----------
OUT = Path(os.environ.get("OUT") or "reports_auto/forensics_fallback")
OUT.mkdir(parents=True, exist_ok=True)

spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

v_spam,   m_spam = load_pipe_meta(spam_pkl)
v_intent, m_int  = load_pipe_meta(intent_pkl)

roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

# 候選集（先放你最可能用到的）
cands = [
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]

# 再掃描（僅 *.jsonl、檔名含 dataset/train/spamassassin；排除 reports_auto/logs）
def under_logs(p: Path) -> bool:
    s = p.as_posix()
    return "/reports_auto/logs/" in s or s.endswith("/reports_auto/logs")

for r in roots:
    if not r.exists(): continue
    for pp in r.rglob("*.jsonl"):
        name = pp.name.lower()
        if (("dataset" in name) or ("train" in name) or ("spamassassin" in name)) and not under_logs(pp):
            cands.append(str(pp))

# 去重
cands = [str(Path(p)) for p in dict.fromkeys(cands)]

rank_intent, rank_spam = [], []
details = {}
for p in cands:
    P = Path(p)
    if not P.exists(): continue
    try:
        s_i, n_i, _ = overlap_score(P, v_intent) if v_intent else (0.0,0,{})
        s_s, n_s, _ = overlap_score(P, v_spam)
        L = label_dist(P)
        entry = {
            "path": str(P),
            "n": int(max(n_i,n_s)),
            "labels": L,
            "size_mb": round(P.stat().st_size/1_000_000, 2)
        }
        rank_intent.append((float(s_i), entry))
        rank_spam.append((float(s_s), entry))
        details[str(P)] = entry
    except Exception as e:
        details[str(P)] = {"path": str(P), "error": repr(e)}

rank_intent.sort(key=lambda x: x[0], reverse=True)
rank_spam.sort(key=lambda x: x[0], reverse=True)

best_intent = (rank_intent[0][1] if rank_intent else None)
best_spam   = (rank_spam[0][1]   if rank_spam   else None)

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:50]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:50]],
    "picked": {"intent": best_intent, "spam": best_spam}
}

(OUT/"FORENSICS.json").write_text(jd(summary), "utf-8")

with open(OUT/"TOP_INTENT.tsv","w",encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_intent[:50],1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")

with open(OUT/"TOP_SPAM.tsv","w",encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_spam[:50],1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")

print(jd({"OUT": str(OUT), "BEST": {"intent": best_intent, "spam": best_spam}}))
PY

python3 "$OUT/forensics.py"
'
++ tee -a reports_auto/panic_20250920T180231/python_stderr.txt
