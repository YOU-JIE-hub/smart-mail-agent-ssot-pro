#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
OUTDIR="reports_auto/inspect/${TS}"
mkdir -p "$OUTDIR"

python - <<'PY'
# -*- coding: utf-8 -*-
import json, re, time, shutil, unicodedata, csv
from pathlib import Path
from collections import Counter, defaultdict

ROOT   = Path(".")
NOW    = time.strftime("%Y%m%dT%H%M%S")
OUTDIR = ROOT / f"reports_auto/inspect/{NOW}"
OUTDIR.mkdir(parents=True, exist_ok=True)

ds_path = ROOT / "data/intent_eval/dataset.jsonl"
if not ds_path.exists() or ds_path.stat().st_size == 0:
    print(f"[FATAL] 找不到資料集或為空：{ds_path.as_posix()}")
    raise SystemExit(2)

def read_jsonl(p: Path):
    out=[]
    broken = OUTDIR/"raw_broken.jsonl"
    for ln in p.read_text("utf-8").splitlines():
        s = ln.strip()
        if not s: continue
        try:
            out.append(json.loads(s))
        except Exception:
            broken.write_text((broken.read_text("utf-8") if broken.exists() else "") + s + "\n", encoding="utf-8")
    return out

def get_text(rec):
    for k in ("text","content","body","subject"):
        if isinstance(rec.get(k), str) and rec[k].strip():
            return rec[k]
    subj = rec.get("subject","") if isinstance(rec.get("subject"), str) else ""
    body = rec.get("body","") if isinstance(rec.get("body"), str) else ""
    if subj or body:
        return (subj + "\n" + body).strip()
    return ""

def get_label(rec):
    for k in ("label","intent","label_true","gold","target","y"):
        v = rec.get(k)
        if isinstance(v,str) and v.strip():
            return v.strip()
    return ""

def norm_text(s:str):
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

rows = read_jsonl(ds_path)

snap_jsonl = OUTDIR / "intent_dataset.jsonl"
snap_csv   = OUTDIR / "intent_dataset.csv"

with snap_jsonl.open("w", encoding="utf-8") as wj, snap_csv.open("w", newline="", encoding="utf-8") as wc:
    cw = csv.writer(wc)
    cw.writerow(["id","label","text"])
    for i,rec in enumerate(rows):
        text = get_text(rec)
        label= get_label(rec)
        j = {"id": i, "label": label, "text": text}
        wj.write(json.dumps(j, ensure_ascii=False) + "\n")
        cw.writerow([i, label, text])

labels = [get_label(r) for r in rows]
cnt = Counter(labels)
total = sum(cnt.values())
dist_md = OUTDIR / "label_counts.md"
with dist_md.open("w", encoding="utf-8") as w:
    w.write("# Intent label counts\n\n")
    w.write(f"- total: {total}\n\n")
    w.write("|label|count|ratio|\n|---|---:|---:|\n")
    for lab, c in cnt.most_common():
        ratio = (c/total) if total else 0.0
        w.write(f"|{lab}|{c}|{ratio:.3f}|\n")

dup_map = defaultdict(list)
for i,rec in enumerate(rows):
    text = get_text(rec)
    label= get_label(rec)
    key  = norm_text(text)
    dup_map[key].append({"id": i, "label": label, "text": text})

dup_groups = [ {"norm_key":k, "count":len(v), "items":v}
               for k,v in dup_map.items() if len(v) >= 2 ]
dup_groups.sort(key=lambda x: (-x["count"], x["norm_key"]))

(OUTDIR/"intent_dups_exact.jsonl").write_text(
    "\n".join(json.dumps(g, ensure_ascii=False) for g in dup_groups),
    encoding="utf-8"
)

with (OUTDIR/"intent_dups_exact_top200.csv").open("w", newline="", encoding="utf-8") as wc:
    cw = csv.writer(wc)
    cw.writerow(["group_rank","group_count","sample_id","sample_label","sample_text"])
    for gi, g in enumerate(dup_groups[:200], start=1):
        for it in g["items"][:5]:
            cw.writerow([gi, g["count"], it["id"], it["label"], it["text"]])

dup_stats = {
    "groups": len(dup_groups),
    "duplicated_items": sum(g["count"] for g in dup_groups),
    "max_group_size": max((g["count"] for g in dup_groups), default=0),
}
(OUTDIR/"intent_dups_stats.json").write_text(json.dumps(dup_stats, ensure_ascii=False, indent=2), encoding="utf-8")

# 抓最新錯分/未匹配
eval_root = ROOT/"reports_auto"/"eval"
if eval_root.exists():
    mis = sorted(eval_root.rglob("intent_miscls*.jsonl"), key=lambda p:p.stat().st_mtime, reverse=True)
    if mis:
        (OUTDIR/"intent_misclass_latest.jsonl").write_text(mis[0].read_text("utf-8"), encoding="utf-8")
    um = sorted(eval_root.rglob("intent_unmatched.jsonl"), key=lambda p:p.stat().st_mtime, reverse=True)
    if um:
        (OUTDIR/"intent_unmatched_latest.jsonl").write_text(um[0].read_text("utf-8"), encoding="utf-8")

# 每類 50 筆樣本，避免 f-string 裡的反斜線：先處理好字串再寫
for lab in cnt:
    keep=0
    fp = OUTDIR / f"sample_{lab}_50.txt"
    with fp.open("w", encoding="utf-8") as w:
        for i,rec in enumerate(rows):
            if get_label(rec) != lab: continue
            txt = get_text(rec).replace("\n"," ").replace("\r"," ")
            w.write(f"[{i}] {txt}\n")
            keep += 1
            if keep>=50: break

manifest = {
    "snapshot_jsonl": (OUTDIR/"intent_dataset.jsonl").as_posix(),
    "snapshot_csv": (OUTDIR/"intent_dataset.csv").as_posix(),
    "label_counts_md": dist_md.as_posix(),
    "dup_exact_jsonl": (OUTDIR/"intent_dups_exact.jsonl").as_posix(),
    "dup_top200_csv":  (OUTDIR/"intent_dups_exact_top200.csv").as_posix(),
    "dup_stats_json":  (OUTDIR/"intent_dups_stats.json").as_posix(),
}
(OUTDIR/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

print("[OK] intent dataset snapshot ->", OUTDIR.as_posix())
print("[HINT] 重要檔案：")
for k,v in manifest.items():
    print(" -", k, ":", v)
PY
