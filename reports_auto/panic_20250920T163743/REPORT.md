# Panic Report
- Exit code: 1
- CMD  : 
set -Eeuo pipefail
cd ~/projects/smart-mail-agent-ssot-pro

# 鎖定你指定的 SPAM；INTENT 用既有 pkl（缺的話只跑 SPAM 偵測）
export SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export INTENT_PKL="${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl}"

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/forensics_${TS}"
mkdir -p "$OUT"
export OUT

python3 - <<'PY'
import os, json, re
from pathlib import Path
from datetime import datetime
from collections import Counter
import joblib

try:
    import numpy as np
except Exception:
    class _NP: pass
    np = _NP()

OUT = Path(os.environ["OUT"])
spam_pkl   = os.environ.get("SPAM_PKL")
intent_pkl = os.environ.get("INTENT_PKL")

# ---------- JSON sanitizer（關鍵修正） ----------
def _json_sanitize(o):
    # numpy 標量
    if "numpy" in o.__class__.__module__:
        try:
            return o.item()
        except Exception:
            pass
    # numpy 陣列
    if hasattr(o, "tolist"):
        try:
            return o.tolist()
        except Exception:
            pass
    if isinstance(o, (set,)):
        return list(o)
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, Counter):
        return dict(o)
    # 其他不認得的型別就轉字串，避免崩潰
    return str(o)

def dumps(obj, **kw):
    kw.setdefault("ensure_ascii", False)
    kw.setdefault("indent", 2)
    kw.setdefault("default", _json_sanitize)
    return json.dumps(obj, **kw)

# ---------- 讀取模型 → 詞彙 ----------
token_re = re.compile(r"[A-Za-z0-9\u4e00-\u9fff_]{2,}")

def load_vocab_from_pipeline(pkl_path):
    meta = {"path": pkl_path, "ok": False}
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

v_spam,   m_spam = load_vocab_from_pipeline(spam_pkl)
v_intent, m_int  = (set(), {"path": intent_pkl, "ok": False})
if intent_pkl and Path(intent_pkl).exists():
    v_intent, m_int = load_vocab_from_pipeline(intent_pkl)

# ---------- 候選清單（高機率處） ----------
candidates = list(dict.fromkeys([
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl",
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/data/spam_eval/dataset.jsonl",
]))

roots = [Path("/home/youjie/projects/smart-mail-agent"),
         Path("/home/youjie/projects/smart-mail-agent_ssot"),
         Path("/home/youjie/projects/smart-mail-agent-ssot-pro")]

for r in roots:
    # 常見路徑別名
    for p in r.rglob("data/**/dataset.jsonl"):
        if "reports_auto/logs" in p.as_posix(): 
            continue
        candidates.append(str(p))
    for p in r.rglob("**/spamassassin.jsonl"):
        candidates.append(str(p))
candidates = list(dict.fromkeys(candidates))

def tokenize(s: str):
    return token_re.findall(s.lower())

def iter_sample_texts(path: str, limit: int = 4000, bytes_cap: int = 40_000_000):
    p = Path(path)
    size = p.stat().st_size
    if size > bytes_cap:
        data = p.open("rb").read(20_000_000).decode("utf-8", errors="ignore").splitlines()
    else:
        data = p.read_text("utf-8", errors="ignore").splitlines()
    n = 0
    for ln in data:
        if not ln.strip():
            continue
        if ln.lstrip().startswith("{"):
            try:
                obj = json.loads(ln)
                for k in ("text","content","body","subject","message"):
                    if isinstance(obj.get(k), str):
                        yield obj[k]; n += 1; break
            except Exception:
                pass
        else:
            yield ln; n += 1
        if n >= limit:
            break

def score_file(path: str, vocab: set[str]):
    if not vocab:
        return 0.0, 0, {}
    seen = Counter()
    n = 0
    for t in iter_sample_texts(path, limit=4000):
        n += 1
        for tok in tokenize(t):
            if tok in vocab:
                seen[tok] += 1
    # 回傳：覆蓋率、樣本數、top tokens
    return (len(seen) / (len(vocab) or 1)), n, dict(seen.most_common(20))

rank_intent, rank_spam = [], []
for p in candidates:
    pp = Path(p)
    if not pp.exists():
        continue
    s_i, n_i, _ = score_file(p, v_intent) if v_intent else (0.0,0,{})
    s_s, n_s, _ = score_file(p, v_spam)
    dist = Counter()
    # 粗略讀前 5k 行抓 label 分佈
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            for i, ln in enumerate(fh, 1):
                if i > 5000: break
                if not ln.strip().startswith("{"): 
                    continue
                try:
                    obj=json.loads(ln)
                    for k in ("label","labels","y","target","intent","category"):
                        if k in obj:
                            v=obj[k]
                            if isinstance(v,(str,int)):
                                dist[str(v)] += 1
                            break
                except Exception:
                    pass
    except Exception:
        pass
    entry = dict(path=str(pp), n=int(max(n_i,n_s)), labels=dict(dist.most_common(8)), size_mb=round(pp.stat().st_size/1_000_000,2))
    rank_intent.append((float(s_i), entry))
    rank_spam.append((float(s_s), entry))

rank_intent.sort(key=lambda x:x[0], reverse=True)
rank_spam.sort(key=lambda x:x[0], reverse=True)
best_intent = (rank_intent[0][1] if rank_intent else None)
best_spam   = (rank_spam[0][1] if rank_spam else None)

summary = {
    "ts": datetime.now().strftime("%Y%m%dT%H%M%S"),
    "models": {"intent": m_int, "spam": m_spam},
    "top_intent": [dict(score=float(s), **e) for s,e in rank_intent[:30]],
    "top_spam":   [dict(score=float(s), **e) for s,e in rank_spam[:30]],
    "picked": {"intent": best_intent, "spam": best_spam},
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT/"FORENSICS.json").write_text(dumps(summary), "utf-8")

with open(OUT/"TOP_INTENT.tsv", "w", encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_intent[:50], 1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")
with open(OUT/"TOP_SPAM.tsv", "w", encoding="utf-8") as f:
    f.write("rank\tscore\tpath\tn\tlabels\tsize_mb\n")
    for i,(s,e) in enumerate(rank_spam[:50], 1):
        f.write(f"{i}\t{float(s):.6f}\t{e[path]}\t{int(e[n])}\t{json.dumps(e[labels],ensure_ascii=False)}\t{e[size_mb]}\n")

print(dumps({"OUT": str(OUT), "BEST": {"intent": best_intent, "spam": best_spam}}))
PY

# 顯示摘要（在 panic 包內也會留下完整紀錄）
LATEST=$(ls -1dt reports_auto/forensics_* | head -1)
echo "[forensics] $LATEST"
[ -n "$LATEST" ] && { sed -n "1,40p" "$LATEST/TOP_INTENT.tsv"; echo; sed -n "1,40p" "$LATEST/TOP_SPAM.tsv"; } || true

- LOG  : reports_auto/panic_20250920T163743/run.log
- ERR  : reports_auto/panic_20250920T163743/run.err
- PY   : reports_auto/panic_20250920T163743/python_stderr.txt
- OOM  : reports_auto/panic_20250920T163743/oom.txt
- TRACE: reports_auto/panic_20250920T163743/xtrace.sh
- SYS  : reports_auto/panic_20250920T163743/system.txt

## Heuristics
