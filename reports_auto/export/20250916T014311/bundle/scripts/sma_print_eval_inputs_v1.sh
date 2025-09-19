#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
OUTDIR="reports_auto/final_check/${TS}"
mkdir -p "$OUTDIR/intent" "$OUTDIR/kie" "$OUTDIR/spam"

echo "[STEP] 蒐集路徑與產出快照..."

python - <<'PY'
# -*- coding: utf-8 -*-
import os, json, csv, hashlib, time
from pathlib import Path
from collections import Counter, defaultdict

ROOT   = Path(".")
NOW    = time.strftime("%Y%m%dT%H%M%S")
OUTDIR = ROOT / f"reports_auto/final_check/{NOW}"
OUTDIR.mkdir(parents=True, exist_ok=True)

def sha256(p: Path):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def read_jsonl(p: Path):
    out=[]
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

def head_lines(text: str, n=20):
    lines=text.splitlines()
    return "\n".join(lines[:n])

manifest = {"generated_at": NOW, "items": []}

# ---------------------- Intent ----------------------
intent = {}
ds_candidates = [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]
for cand in ds_candidates:
    if cand.exists() and cand.stat().st_size>0:
        intent["dataset_path"] = cand.as_posix()
        ds = read_jsonl(cand)
        intent["size"] = len(ds)
        # label 統計
        cnt = Counter()
        for r in ds:
            y = r.get("label") or r.get("y") or r.get("intent")
            if y: cnt[y]+=1
        intent["label_counts"] = dict(sorted(cnt.items(), key=lambda x: (-x[1], x[0])))
        # 快照與校驗
        snap = OUTDIR/"intent"/cand.name
        snap.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in ds), "utf-8")
        intent["sha256"] = sha256(snap)
        intent["snapshot"] = snap.as_posix()
        # 產 CSV 快速檢視
        csvp = OUTDIR/"intent"/(cand.stem+".csv")
        import csv as _csv
        with csvp.open("w", newline="", encoding="utf-8") as w:
            wr = _csv.writer(w)
            wr.writerow(["id","label","text"])
            for r in ds:
                wr.writerow([r.get("id",""), r.get("label") or r.get("y") or r.get("intent",""), r.get("text","").replace("\n"," ")[:500]])
        intent["snapshot_csv"] = csvp.as_posix()
        break

# 蒐集最新意圖評估資料夾（FN/FP/miscls/calib）
eval_dirs = sorted((ROOT/"reports_auto/eval").glob("*/"), key=lambda p:p.stat().st_mtime, reverse=True)
for d in eval_dirs:
    cand = d/"metrics_intent_rules_hotfix_v11c.md"
    if cand.exists():
        intent["metrics"] = cand.as_posix()
        # FN/FP
        fnfps = list(d.glob("FN_*.txt")) + list(d.glob("FP_*.txt"))
        dump_dir = OUTDIR/"intent"/"errors"
        dump_dir.mkdir(parents=True, exist_ok=True)
        copied=[]
        for f in fnfps:
            tgt = dump_dir/f.name
            tgt.write_text(f.read_text("utf-8"), "utf-8")
            copied.append(tgt.as_posix())
        if copied: intent["fn_fp_dump"] = copied
        # misclass
        for m in ["intent_miscls_v11c.jsonl","intent_miscls_v11b.jsonl","intent_miscls_v10.jsonl","intent_miscls_v9.jsonl","intent_miscls_v8.jsonl"]:
            p = d/m
            if p.exists():
                tgt = OUTDIR/"intent"/p.name
                tgt.write_text(p.read_text("utf-8"), "utf-8")
                intent["misclass_dump"] = tgt.as_posix()
                break
        break

calib = ROOT/"artifacts_prod/intent_rules_calib_v11c.json"
if calib.exists():
    tgt = OUTDIR/"intent"/calib.name
    tgt.write_text(calib.read_text("utf-8"), "utf-8")
    intent["calibration"] = {"path": tgt.as_posix(), "sha256": sha256(tgt)}

manifest["items"].append({"task":"intent","detail":intent})

# ---------------------- KIE ----------------------
kie = {}
gold = ROOT/"data/kie_eval/gold_merged.jsonl"
if gold.exists():
    ds = read_jsonl(gold)
    kie["gold_path"] = gold.as_posix()
    kie["gold_size"] = len(ds)
    # label 統計（以 span.label）
    from collections import Counter as C
    cc = C()
    for r in ds:
        for sp in (r.get("spans") or []):
            lb = sp.get("label")
            if lb: cc[lb]+=1
    kie["gold_label_counts"] = dict(sorted(cc.items(), key=lambda x:(-x[1],x[0])))
    tgt = OUTDIR/"kie"/gold.name
    tgt.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in ds), "utf-8")
    kie["gold_snapshot"] = tgt.as_posix()
    kie["gold_sha256"] = sha256(tgt)

# 最新 hybrid 預測與 metrics
kie_dirs = sorted((ROOT/"reports_auto/kie_eval").glob("*/"), key=lambda p:p.stat().st_mtime, reverse=True)
for d in kie_dirs:
    pred = d/"hybrid_preds.jsonl"
    met  = d/"metrics_kie_spans.md"
    if pred.exists() and met.exists():
        tgtp = OUTDIR/"kie"/pred.name
        tgtp.write_text(pred.read_text("utf-8"), "utf-8")
        tgtm = OUTDIR/"kie"/met.name
        tgtm.write_text(met.read_text("utf-8"), "utf-8")
        kie["pred_snapshot"] = tgtp.as_posix()
        kie["pred_sha256"]   = sha256(tgtp)
        kie["metrics"]       = tgtm.as_posix()
        break

manifest["items"].append({"task":"kie","detail":kie})

# ---------------------- Spam ----------------------
spam={}
pred = ROOT/"artifacts_prod/text_predictions_test.tsv"
if pred.exists():
    txt = pred.read_text("utf-8", errors="ignore")
    rows = len(txt.splitlines())-1 if "\n" in txt else 0
    spam["pred_path"] = pred.as_posix()
    spam["rows"] = rows
    tgt = OUTDIR/"spam"/pred.name
    tgt.write_text(txt, "utf-8")
    spam["pred_snapshot"] = tgt.as_posix()
    spam["pred_sha256"] = sha256(tgt)
th = ROOT/"artifacts_prod/ens_thresholds.json"
if th.exists():
    tgt = OUTDIR/"spam"/th.name
    tgt.write_text(th.read_text("utf-8"), "utf-8")
    spam["thresholds"] = {"path": tgt.as_posix(), "sha256": sha256(tgt)}

# 最新 spam metrics
for d in eval_dirs:
    met = d/"metrics_spam_autocal_v4.md"
    if met.exists():
        tgtm = OUTDIR/"spam"/met.name
        tgtm.write_text(met.read_text("utf-8"), "utf-8")
        spam["metrics"] = tgtm.as_posix()
        break

manifest["items"].append({"task":"spam","detail":spam})

# ---------------------- 輸出 manifest ----------------------
(OUTDIR/"DATA_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")

# 產生可讀版 MD
md = ["# Final Check Data Manifest",
      f"- generated_at: `{NOW}`",
      ""]
for it in manifest["items"]:
    md.append(f"## {it['task'].upper()}")
    for k,v in it["detail"].items():
        if isinstance(v, dict):
            md.append(f"- {k}: `{v.get('path','')}` (sha256={v.get('sha256','')})")
        elif isinstance(v, list):
            if v and isinstance(v[0], str):
                md.append(f"- {k}:")
                for s in v[:10]:
                    md.append(f"  - `{s}`")
                if len(v)>10: md.append(f"  - ... ({len(v)} files)")
        else:
            md.append(f"- {k}: `{v}`")
    md.append("")
(OUTDIR/"DATA_MANIFEST.md").write_text("\n".join(md), "utf-8")

print(f"[OK] final check manifest -> { (OUTDIR/'DATA_MANIFEST.md').as_posix() }")
PY

echo "[STEP] 節選重點內容到終端（各 20 行）"
echo "---- INTENT dataset head ----"
python - <<'PY'
from pathlib import Path, PurePath
import json, time
ROOT=Path(".")
snap_dirs=sorted((ROOT/"reports_auto/final_check").glob("*/intent"), key=lambda p:p.stat().st_mtime, reverse=True)
if snap_dirs:
    ds = None
    for cand in ["dataset.cleaned.jsonl", "dataset.jsonl"]:
        p = snap_dirs[0]/cand
        if p.exists():
            ds = p; break
    if ds:
        lines = ds.read_text("utf-8").splitlines()
        for ln in lines[:20]:
            print(ln)
PY

echo "---- KIE gold head ----"
python - <<'PY'
from pathlib import Path
ROOT=Path(".")
snap_dirs=sorted((ROOT/"reports_auto/final_check").glob("*/kie"), key=lambda p:p.stat().st_mtime, reverse=True)
if snap_dirs:
    p = snap_dirs[0]/"gold_merged.jsonl"
    if p.exists():
        lines = p.read_text("utf-8").splitlines()
        for ln in lines[:20]:
            print(ln)
PY

echo "---- SPAM preds head ----"
python - <<'PY'
from pathlib import Path
ROOT=Path(".")
snap_dirs=sorted((ROOT/"reports_auto/final_check").glob("*/spam"), key=lambda p:p.stat().st_mtime, reverse=True)
if snap_dirs:
    p = snap_dirs[0]/"text_predictions_test.tsv"
    if p.exists():
        for i,ln in enumerate(p.read_text("utf-8", errors="ignore").splitlines()[:20]):
            print(ln)
PY

echo ">>> Manifest 路徑：$(ls -t reports_auto/final_check/*/DATA_MANIFEST.md | head -n1)"
