#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
OUTDIR="reports_auto/intent_autofix/${TS}"
mkdir -p "$OUTDIR" "reports_auto/status" "data/intent_eval"

python - <<'PY'
# -*- coding: utf-8 -*-
import json, re, time, unicodedata, csv, hashlib, math, os
from pathlib import Path
from collections import Counter, defaultdict

ROOT   = Path(".")
NOW    = time.strftime("%Y%m%dT%H%M%S")
OUTDIR = ROOT / f"reports_auto/intent_autofix/{NOW}"
OUTDIR.mkdir(parents=True, exist_ok=True)

ALLOW = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]
ALLOW_SET = set(ALLOW)

# 1) 找資料集來源（優先 data/intent_eval/dataset.jsonl，否則找最新快照）
ds_main = ROOT/"data/intent_eval/dataset.jsonl"
if not ds_main.exists() or ds_main.stat().st_size == 0:
    snaps = sorted((ROOT/"reports_auto/inspect").glob("*/intent_dataset.jsonl"), key=lambda p:p.stat().st_mtime, reverse=True)
    if snaps:
        ds_main = snaps[0]
if not ds_main.exists() or ds_main.stat().st_size == 0:
    raise SystemExit(f"[FATAL] 找不到資料集：{ds_main.as_posix()}")

def read_jsonl(p):
    out=[]
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out

def get_text(r):
    # 容錯取文：text/subject/body/title/summary…有就組起來
    for k in ["text","content","message","utterance"]:
        if k in r and isinstance(r[k], str) and r[k].strip():
            return r[k]
    subj = r.get("subject","") or r.get("title","")
    body = r.get("body","") or r.get("desc","") or r.get("description","")
    joined = " ".join([x for x in [subj, body] if isinstance(x,str) and x.strip()])
    return joined.strip()

def norm_text(s):
    s = unicodedata.normalize("NFKC", s).casefold()
    # 把網址/票號簡化
    s = re.sub(r"https?://\S+", " <URL> ", s)
    s = re.sub(r"[A-Z0-9]{6,}", " <ID> ", s)  # 粗略票號遮罩
    # 數字歸一化
    s = re.sub(r"\d+", "0", s)
    # 空白歸一
    s = re.sub(r"\s+", " ", s).strip()
    return s

def pattern_key(s):
    # 更激進：去除多餘符號、把數字與貨幣統一化，抓「模板化語句」
    x = unicodedata.normalize("NFKC", s).casefold()
    x = re.sub(r"\d+", "0", x)
    x = re.sub(r"nt\$|usd|\$|元|台幣|twd", "<CUR>", x)
    x = re.sub(r"[^\w\u4e00-\u9fff<>\s]", " ", x)  # 去符號
    x = re.sub(r"\s+", " ", x).strip()
    return x

def jaccard(a, b):
    if not a or not b: return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb); union = len(sa | sb)
    return inter/union if union else 0.0

def tokenize(s):
    # 混中英：先分詞到字/詞邊界，避免額外依賴
    s = re.sub(r"[^\w\u4e00-\u9fff]+", " ", s)
    # 簡單：連續中文字切成單字，英文/數字保留 token
    toks=[]
    buf=[]
    for ch in s:
        if u'\u4e00' <= ch <= u'\u9fff':
            if buf:
                toks.append("".join(buf)); buf=[]
            toks.append(ch)
        else:
            buf.append(ch)
    if buf: toks.append("".join(buf))
    toks=[t for t in toks if t and t.strip()]
    return toks

recs = read_jsonl(ds_main)
before_cnt = len(recs)

# 2) 基本清洗與標籤容錯
clean=[]
bad_label=[]
for r in recs:
    lab = r.get("label") or r.get("intent") or r.get("y")
    if isinstance(lab, str): lab = lab.strip()
    if lab not in ALLOW_SET:
        bad_label.append(r)
        continue
    txt = get_text(r)
    if not isinstance(txt, str) or not txt.strip():
        continue
    clean.append({"label": lab, "text": txt.strip()})

# 3) exact 去重（norm_text）
seen = {}
dedup_exact = []
removed_exact = []
for r in clean:
    k = (r["label"], norm_text(r["text"]))
    if k in seen:
        removed_exact.append(r)
        continue
    seen[k]=True
    dedup_exact.append(r)

# 4) template/近重 去重（pattern_key + jaccard token 相似度）
# 先按 pattern_key 聚類，再在每群內做簡易近重
clusters = defaultdict(list)
for r in dedup_exact:
    pk = (r["label"], pattern_key(r["text"]))
    clusters[pk].append(r)

kept=[]
removed_near=[]
for pk, items in clusters.items():
    if len(items) == 1:
        kept.extend(items); continue
    # 以第一個為代表，後續高相似（>=0.9）就移除
    # 為穩定可多代表：這裡用簡單策略以控制複雜度
    reps=[]  # 代表們（避免 O(n^2)）
    for r in items:
        toks = tokenize(norm_text(r["text"]))
        is_dup=False
        for rep in reps:
            if jaccard(toks, rep["toks"]) >= 0.90:
                removed_near.append(r)
                is_dup=True
                break
        if not is_dup:
            reps.append({"toks": toks, "rec": r})
            kept.append(r)

# 5) 匯出
def write_jsonl(path, arr):
    with open(path, "w", encoding="utf-8") as w:
        for obj in arr:
            w.write(json.dumps(obj, ensure_ascii=False)+"\n")

# 最終清單
final_path_jsonl = ROOT/"data/intent_eval/dataset.cleaned.jsonl"
final_path_csv    = ROOT/"data/intent_eval/dataset.cleaned.csv"
write_jsonl(final_path_jsonl, kept)
with open(final_path_csv, "w", encoding="utf-8", newline="") as f:
    wr=csv.writer(f)
    wr.writerow(["label","text"])
    for r in kept:
        wr.writerow([r["label"], r["text"].replace("\n"," ")])

# 審閱輸出
write_jsonl(OUTDIR/"removed_exact.jsonl", removed_exact)
write_jsonl(OUTDIR/"removed_near.jsonl", removed_near)
with open(OUTDIR/"near_clusters_stats.md","w",encoding="utf-8") as w:
    w.write("# Near-duplicate cluster sizes (top)\n")
    sizes = sorted([(k,len(v)) for k,v in clusters.items()], key=lambda x:x[1], reverse=True)
    for k,sz in sizes[:200]:
        w.write(f"{k[0]}\t{sz}\t{k[1]}\n")

# 6) 標籤分布（前/後）
def label_counts(arr):
    c=Counter([r["label"] for r in arr])
    return {k:int(c.get(k,0)) for k in ALLOW}

with open(OUTDIR/"label_counts_before_after.md","w",encoding="utf-8") as w:
    bc = label_counts(clean)
    ac = label_counts(kept)
    w.write("# Label counts (before -> after)\n")
    for k in ALLOW:
        w.write(f"- {k}: {bc.get(k,0)} -> {ac.get(k,0)}\n")

# 7) 產生抽樣檢視集（各類各抽 50）
def sample_by_label(arr, n=50):
    bucket=defaultdict(list)
    for r in arr:
        if len(bucket[r["label"]])<n:
            bucket[r["label"]].append(r)
    out=[]
    for k in ALLOW:
        out.extend(bucket[k])
    return out

write_jsonl(OUTDIR/"sample_cleaned_per_label_50.jsonl", sample_by_label(kept, 50))

# 8) Summary
msg = []
msg.append(f"[INFO] source: {ds_main.as_posix()}")
msg.append(f"[INFO] loaded: {before_cnt}")
msg.append(f"[INFO] bad_label_dropped: {len(bad_label)}")
msg.append(f"[INFO] kept_after_exact: {len(dedup_exact)}  removed_exact: {len(removed_exact)}")
msg.append(f"[INFO] kept_final: {len(kept)}  removed_near: {len(removed_near)}")
msg.append(f"[OK] cleaned jsonl -> {Path('data/intent_eval/dataset.cleaned.jsonl').as_posix()}")
msg.append(f"[OK] cleaned csv  -> {Path('data/intent_eval/dataset.cleaned.csv').as_posix()}")
msg.append(f"[OK] review pack -> {OUTDIR.as_posix()}")
print("\n".join(msg))
PY
