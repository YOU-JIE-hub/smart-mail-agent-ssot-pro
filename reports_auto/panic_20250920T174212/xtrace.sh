+ CMD='
set -Eeuo pipefail
cd ~/projects/smart-mail-agent-ssot-pro

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（缺就只用 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - << "PY"
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

def _json_sanitize(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer, np.floating, np.bool_)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return list(o)
    if isinstance(o, Counter): return dict(o)
    if isinstance(o, Path): return str(o)
    return o

def jd(x): return json.dumps(x, ensure_ascii=False, indent=2, default=_json_sanitize)

# --------- 基本設定 ---------
OUT = Path(os.environ.get("OUT") or "reports_auto/forensics_fallback")
OUT.mkdir(parents=True, exist_ok=True)

spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")

def load_vocab_from_pipeline(pkl_path):
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

def tokenize(s:str): return token_re.findall(s.lower())

def sample_lines(path: Path, limit=4000, bytes_cap=40_000_000):
    try:
        size = path.stat().st_size
        if size > bytes_cap:
            data = path.open("rb").read(20_000_000).decode("utf-8","ignore").splitlines()
        else:
            data = path.read_text("utf-8","ignore").splitlines()
        n = 0
        for ln in data:
            ln = ln.strip()
            if not ln: continue
            yield ln
            n += 1
            if n >= limit: break
    except Exception:
        return

def iter_texts(path: Path, limit=4000):
    n = 0
    for ln in sample_lines(path, limit=limit):
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message"):
                    v = obj.get(k)
                    if isinstance(v,str) and v.strip():
                        yield v; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit: break

def score_file(pp: Path, vocab: set[str]):
    if not vocab: return 0.0, 0, {}
    seen = Counter(); n = 0
    for t in iter_texts(pp):
        n += 1
        for tok in tokenize(t):
            if tok in vocab: seen[tok] += 1
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(20))

def label_dist(pp: Path):
    dist = Counter()
    for ln in sample_lines(pp, limit=5000):
        if not ln.startswith("{"): continue
        try:
            obj = json.loads(ln)
            for k in ("label","labels","y","target","intent","category"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v,(str,int)): dist[str(v)] += 1
                    break
        except Exception:
            pass
    return dict(dist.most_common(10))

# 1) 讀模型詞彙
v_spam,   m_spam = load_vocab_from_pipeline(spam_pkl)
v_intent, m_int  = load_vocab_from_pipeline(intent_pkl)

# 2) 候選資料集（含常見位置 + 掃描）
roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

candidates = list(dict.fromkeys([
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]))

def under_logs(p: Path) -> bool:
    s = p.as_posix()
    return "/reports_auto/logs/" in s or s.endswith("/reports_auto/logs")

for r in roots:
    if not r.exists(): continue
    for pp in r.rglob("*.jsonl"):
        n = pp.name.lower()
        if ("dataset" in n or "train" in n or "spamassassin" in n) and not under_logs(pp):
            candidates.append(str(pp))
    for pp in r.rglob("*.json"):
        if "spamassassin" in pp.name.lower() and not under_logs(pp):
            candidates.append(str(pp))

candidates = [str(Path(p)) for p in dict.fromkeys(candidates)]

# 3) 根據兩個模型詞彙計分
rank_intent, rank_spam = [], []
for p in candidates:
    pp = Path(p)
    if not pp.exists(): continue
    s_i, n_i, _ = score_file(pp, v_intent) if v_intent else (0.0,0,{})
    s_s, n_s, _ = score_file(pp, v_spam)
    entry = {"path": str(pp), "n": int(max(n_i,n_s)), "labels": label_dist(pp),
             "size_mb": round(pp.stat().st_size/1_000_000, 2)}
    rank_intent.append((float(s_i), entry))
    rank_spam.append((float(s_s), entry))

rank_intent.sort(key=lambda x:x[0], reverse=True)
rank_spam.sort(key=lambda x:x[0], reverse=True)
best_intent = rank_intent[0][1] if rank_intent else None
best_spam   = rank_spam[0][1]   if rank_spam   else None

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:50]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:50]],
    "picked": {"intent": best_intent, "spam": best_spam},
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
'
+ '[' -z '
set -Eeuo pipefail
cd ~/projects/smart-mail-agent-ssot-pro

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（缺就只用 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - << "PY"
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

def _json_sanitize(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer, np.floating, np.bool_)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return list(o)
    if isinstance(o, Counter): return dict(o)
    if isinstance(o, Path): return str(o)
    return o

def jd(x): return json.dumps(x, ensure_ascii=False, indent=2, default=_json_sanitize)

# --------- 基本設定 ---------
OUT = Path(os.environ.get("OUT") or "reports_auto/forensics_fallback")
OUT.mkdir(parents=True, exist_ok=True)

spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")

def load_vocab_from_pipeline(pkl_path):
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

def tokenize(s:str): return token_re.findall(s.lower())

def sample_lines(path: Path, limit=4000, bytes_cap=40_000_000):
    try:
        size = path.stat().st_size
        if size > bytes_cap:
            data = path.open("rb").read(20_000_000).decode("utf-8","ignore").splitlines()
        else:
            data = path.read_text("utf-8","ignore").splitlines()
        n = 0
        for ln in data:
            ln = ln.strip()
            if not ln: continue
            yield ln
            n += 1
            if n >= limit: break
    except Exception:
        return

def iter_texts(path: Path, limit=4000):
    n = 0
    for ln in sample_lines(path, limit=limit):
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message"):
                    v = obj.get(k)
                    if isinstance(v,str) and v.strip():
                        yield v; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit: break

def score_file(pp: Path, vocab: set[str]):
    if not vocab: return 0.0, 0, {}
    seen = Counter(); n = 0
    for t in iter_texts(pp):
        n += 1
        for tok in tokenize(t):
            if tok in vocab: seen[tok] += 1
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(20))

def label_dist(pp: Path):
    dist = Counter()
    for ln in sample_lines(pp, limit=5000):
        if not ln.startswith("{"): continue
        try:
            obj = json.loads(ln)
            for k in ("label","labels","y","target","intent","category"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v,(str,int)): dist[str(v)] += 1
                    break
        except Exception:
            pass
    return dict(dist.most_common(10))

# 1) 讀模型詞彙
v_spam,   m_spam = load_vocab_from_pipeline(spam_pkl)
v_intent, m_int  = load_vocab_from_pipeline(intent_pkl)

# 2) 候選資料集（含常見位置 + 掃描）
roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

candidates = list(dict.fromkeys([
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]))

def under_logs(p: Path) -> bool:
    s = p.as_posix()
    return "/reports_auto/logs/" in s or s.endswith("/reports_auto/logs")

for r in roots:
    if not r.exists(): continue
    for pp in r.rglob("*.jsonl"):
        n = pp.name.lower()
        if ("dataset" in n or "train" in n or "spamassassin" in n) and not under_logs(pp):
            candidates.append(str(pp))
    for pp in r.rglob("*.json"):
        if "spamassassin" in pp.name.lower() and not under_logs(pp):
            candidates.append(str(pp))

candidates = [str(Path(p)) for p in dict.fromkeys(candidates)]

# 3) 根據兩個模型詞彙計分
rank_intent, rank_spam = [], []
for p in candidates:
    pp = Path(p)
    if not pp.exists(): continue
    s_i, n_i, _ = score_file(pp, v_intent) if v_intent else (0.0,0,{})
    s_s, n_s, _ = score_file(pp, v_spam)
    entry = {"path": str(pp), "n": int(max(n_i,n_s)), "labels": label_dist(pp),
             "size_mb": round(pp.stat().st_size/1_000_000, 2)}
    rank_intent.append((float(s_i), entry))
    rank_spam.append((float(s_s), entry))

rank_intent.sort(key=lambda x:x[0], reverse=True)
rank_spam.sort(key=lambda x:x[0], reverse=True)
best_intent = rank_intent[0][1] if rank_intent else None
best_spam   = rank_spam[0][1]   if rank_spam   else None

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:50]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:50]],
    "picked": {"intent": best_intent, "spam": best_spam},
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
' ']'
+ echo '== SNAPSHOT 20250920T174212 =='
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

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（缺就只用 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - << "PY"
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

def _json_sanitize(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer, np.floating, np.bool_)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return list(o)
    if isinstance(o, Counter): return dict(o)
    if isinstance(o, Path): return str(o)
    return o

def jd(x): return json.dumps(x, ensure_ascii=False, indent=2, default=_json_sanitize)

# --------- 基本設定 ---------
OUT = Path(os.environ.get("OUT") or "reports_auto/forensics_fallback")
OUT.mkdir(parents=True, exist_ok=True)

spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")

def load_vocab_from_pipeline(pkl_path):
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

def tokenize(s:str): return token_re.findall(s.lower())

def sample_lines(path: Path, limit=4000, bytes_cap=40_000_000):
    try:
        size = path.stat().st_size
        if size > bytes_cap:
            data = path.open("rb").read(20_000_000).decode("utf-8","ignore").splitlines()
        else:
            data = path.read_text("utf-8","ignore").splitlines()
        n = 0
        for ln in data:
            ln = ln.strip()
            if not ln: continue
            yield ln
            n += 1
            if n >= limit: break
    except Exception:
        return

def iter_texts(path: Path, limit=4000):
    n = 0
    for ln in sample_lines(path, limit=limit):
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message"):
                    v = obj.get(k)
                    if isinstance(v,str) and v.strip():
                        yield v; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit: break

def score_file(pp: Path, vocab: set[str]):
    if not vocab: return 0.0, 0, {}
    seen = Counter(); n = 0
    for t in iter_texts(pp):
        n += 1
        for tok in tokenize(t):
            if tok in vocab: seen[tok] += 1
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(20))

def label_dist(pp: Path):
    dist = Counter()
    for ln in sample_lines(pp, limit=5000):
        if not ln.startswith("{"): continue
        try:
            obj = json.loads(ln)
            for k in ("label","labels","y","target","intent","category"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v,(str,int)): dist[str(v)] += 1
                    break
        except Exception:
            pass
    return dict(dist.most_common(10))

# 1) 讀模型詞彙
v_spam,   m_spam = load_vocab_from_pipeline(spam_pkl)
v_intent, m_int  = load_vocab_from_pipeline(intent_pkl)

# 2) 候選資料集（含常見位置 + 掃描）
roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

candidates = list(dict.fromkeys([
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]))

def under_logs(p: Path) -> bool:
    s = p.as_posix()
    return "/reports_auto/logs/" in s or s.endswith("/reports_auto/logs")

for r in roots:
    if not r.exists(): continue
    for pp in r.rglob("*.jsonl"):
        n = pp.name.lower()
        if ("dataset" in n or "train" in n or "spamassassin" in n) and not under_logs(pp):
            candidates.append(str(pp))
    for pp in r.rglob("*.json"):
        if "spamassassin" in pp.name.lower() and not under_logs(pp):
            candidates.append(str(pp))

candidates = [str(Path(p)) for p in dict.fromkeys(candidates)]

# 3) 根據兩個模型詞彙計分
rank_intent, rank_spam = [], []
for p in candidates:
    pp = Path(p)
    if not pp.exists(): continue
    s_i, n_i, _ = score_file(pp, v_intent) if v_intent else (0.0,0,{})
    s_s, n_s, _ = score_file(pp, v_spam)
    entry = {"path": str(pp), "n": int(max(n_i,n_s)), "labels": label_dist(pp),
             "size_mb": round(pp.stat().st_size/1_000_000, 2)}
    rank_intent.append((float(s_i), entry))
    rank_spam.append((float(s_s), entry))

rank_intent.sort(key=lambda x:x[0], reverse=True)
rank_spam.sort(key=lambda x:x[0], reverse=True)
best_intent = rank_intent[0][1] if rank_intent else None
best_spam   = rank_spam[0][1]   if rank_spam   else None

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:50]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:50]],
    "picked": {"intent": best_intent, "spam": best_spam},
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
'
++ tee -a reports_auto/panic_20250920T174212/python_stderr.txt
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
cd ~/projects/smart-mail-agent-ssot-pro

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（缺就只用 SPAM）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - << "PY"
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

def _json_sanitize(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer, np.floating, np.bool_)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return list(o)
    if isinstance(o, Counter): return dict(o)
    if isinstance(o, Path): return str(o)
    return o

def jd(x): return json.dumps(x, ensure_ascii=False, indent=2, default=_json_sanitize)

# --------- 基本設定 ---------
OUT = Path(os.environ.get("OUT") or "reports_auto/forensics_fallback")
OUT.mkdir(parents=True, exist_ok=True)

spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")

def load_vocab_from_pipeline(pkl_path):
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

def tokenize(s:str): return token_re.findall(s.lower())

def sample_lines(path: Path, limit=4000, bytes_cap=40_000_000):
    try:
        size = path.stat().st_size
        if size > bytes_cap:
            data = path.open("rb").read(20_000_000).decode("utf-8","ignore").splitlines()
        else:
            data = path.read_text("utf-8","ignore").splitlines()
        n = 0
        for ln in data:
            ln = ln.strip()
            if not ln: continue
            yield ln
            n += 1
            if n >= limit: break
    except Exception:
        return

def iter_texts(path: Path, limit=4000):
    n = 0
    for ln in sample_lines(path, limit=limit):
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message"):
                    v = obj.get(k)
                    if isinstance(v,str) and v.strip():
                        yield v; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit: break

def score_file(pp: Path, vocab: set[str]):
    if not vocab: return 0.0, 0, {}
    seen = Counter(); n = 0
    for t in iter_texts(pp):
        n += 1
        for tok in tokenize(t):
            if tok in vocab: seen[tok] += 1
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(20))

def label_dist(pp: Path):
    dist = Counter()
    for ln in sample_lines(pp, limit=5000):
        if not ln.startswith("{"): continue
        try:
            obj = json.loads(ln)
            for k in ("label","labels","y","target","intent","category"):
                if k in obj:
                    v = obj[k]
                    if isinstance(v,(str,int)): dist[str(v)] += 1
                    break
        except Exception:
            pass
    return dict(dist.most_common(10))

# 1) 讀模型詞彙
v_spam,   m_spam = load_vocab_from_pipeline(spam_pkl)
v_intent, m_int  = load_vocab_from_pipeline(intent_pkl)

# 2) 候選資料集（含常見位置 + 掃描）
roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

candidates = list(dict.fromkeys([
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]))

def under_logs(p: Path) -> bool:
    s = p.as_posix()
    return "/reports_auto/logs/" in s or s.endswith("/reports_auto/logs")

for r in roots:
    if not r.exists(): continue
    for pp in r.rglob("*.jsonl"):
        n = pp.name.lower()
        if ("dataset" in n or "train" in n or "spamassassin" in n) and not under_logs(pp):
            candidates.append(str(pp))
    for pp in r.rglob("*.json"):
        if "spamassassin" in pp.name.lower() and not under_logs(pp):
            candidates.append(str(pp))

candidates = [str(Path(p)) for p in dict.fromkeys(candidates)]

# 3) 根據兩個模型詞彙計分
rank_intent, rank_spam = [], []
for p in candidates:
    pp = Path(p)
    if not pp.exists(): continue
    s_i, n_i, _ = score_file(pp, v_intent) if v_intent else (0.0,0,{})
    s_s, n_s, _ = score_file(pp, v_spam)
    entry = {"path": str(pp), "n": int(max(n_i,n_s)), "labels": label_dist(pp),
             "size_mb": round(pp.stat().st_size/1_000_000, 2)}
    rank_intent.append((float(s_i), entry))
    rank_spam.append((float(s_s), entry))

rank_intent.sort(key=lambda x:x[0], reverse=True)
rank_spam.sort(key=lambda x:x[0], reverse=True)
best_intent = rank_intent[0][1] if rank_intent else None
best_spam   = rank_spam[0][1]   if rank_spam   else None

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:50]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:50]],
    "picked": {"intent": best_intent, "spam": best_spam},
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
'
+ echo '- LOG  : reports_auto/panic_20250920T174212/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T174212/run.err'
+ echo '- PY   : reports_auto/panic_20250920T174212/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T174212/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T174212/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T174212/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T174212/run.err reports_auto/panic_20250920T174212/python_stderr.txt
+ grep -qi 'No module named '\''tools'\''' reports_auto/panic_20250920T174212/run.err reports_auto/panic_20250920T174212/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T174212/run.err reports_auto/panic_20250920T174212/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T174212/run.err reports_auto/panic_20250920T174212/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T174212/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ printf '%s\n' reports_auto/panic_20250920T174212/REPORT.md reports_auto/panic_20250920T174212/run.log reports_auto/panic_20250920T174212/run.err reports_auto/panic_20250920T174212/python_stderr.txt reports_auto/panic_20250920T174212/xtrace.sh reports_auto/panic_20250920T174212/system.txt reports_auto/panic_20250920T174212/oom.txt
+ echo
+ exit 1
