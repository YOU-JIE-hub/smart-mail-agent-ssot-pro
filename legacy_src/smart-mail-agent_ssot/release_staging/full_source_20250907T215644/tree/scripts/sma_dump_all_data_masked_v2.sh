#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/final_dump/${TS}"
mkdir -p "$OUT/intent" "$OUT/kie" "$OUT/spam" "reports_auto/status"

python - <<'PY'
# -*- coding: utf-8 -*-
import os, re, json, csv, time, hashlib, tarfile
from pathlib import Path

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
OUT = ROOT/f"reports_auto/final_dump/{NOW}"
(OUT/"intent").mkdir(parents=True, exist_ok=True)
(OUT/"kie").mkdir(parents=True, exist_ok=True)
(OUT/"spam").mkdir(parents=True, exist_ok=True)

def sha256(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for ch in iter(lambda:f.read(1<<20), b""):
            h.update(ch)
    return h.hexdigest()

def mask_general(text: str) -> str:
    if not text: return text
    t = text
    t = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<EMAIL>", t)
    t = re.sub(r"(https?://|www\.)\S+", "<URL>", t)
    t = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<IP>", t)
    t = re.sub(r"\+?\d[\d\s\-()]{6,}\d", "<PHONE>", t)
    t = re.sub(r"(USD|NT\$|NTD|TWD|\$)\s?\d[\d,]*(?:\.\d+)?", "<AMOUNT>", t, flags=re.I)
    t = re.sub(r"\b[A-Z]{2}\d{8}\b", "<ID>", t)
    return t

def mask_fixed_len(text: str) -> str:
    if not text: return text
    out=[]
    for ch in text:
        if "0" <= ch <= "9": out.append("0")
        elif "A" <= ch <= "Z": out.append("X")
        elif "a" <= ch <= "z": out.append("x")
        elif re.match(r"[\u4e00-\u9fff]", ch): out.append("＊")
        else: out.append(ch)
    return "".join(out)

def write_jsonl(path: Path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), "utf-8")

MAN = ["# DATA MANIFEST", "", "| file | bytes | sha256 |", "|---|---:|---|"]
def keep(p: Path):
    MAN.append(f"| `{p.as_posix()}` | {p.stat().st_size} | `{sha256(p)}` |")

# -------- Intent dataset --------
intent_src=None
for cand in [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if cand.exists() and cand.stat().st_size>0:
        intent_src=cand; break

if intent_src:
    rows=[]
    for ln in intent_src.read_text("utf-8",errors="ignore").splitlines():
        if not ln.strip(): continue
        rec=json.loads(ln)
        rows.append({"label": rec.get("label") or rec.get("intent"), "text": mask_general(rec.get("text",""))})
    jpath=OUT/"intent/intent_dataset_masked.jsonl"; write_jsonl(jpath, rows); keep(jpath)
    cpath=OUT/"intent/intent_dataset_masked.csv"
    with cpath.open("w", newline="", encoding="utf-8") as w:
        import csv; wr=csv.writer(w); wr.writerow(["label","text"])
        for r in rows: wr.writerow([r["label"], r["text"]])
    keep(cpath)

# 近期評估衍生：重覆、誤判、未覆蓋等（若存在就帶走）
for globpat in [
    "reports_auto/inspect/*/intent_dups_exact.jsonl",
    "reports_auto/eval/*/intent_miscls_v*.jsonl",
    "reports_auto/eval/*/intent_unmatched.jsonl",
]:
    for fp in sorted(ROOT.glob(globpat), key=lambda p:p.stat().st_mtime, reverse=True)[:3]:
        try:
            rows=[]
            for ln in fp.read_text("utf-8",errors="ignore").splitlines():
                if not ln.strip(): continue
                obj=json.loads(ln)
                if "text" in obj: obj["text"]=mask_general(obj["text"])
                rows.append(obj)
            outp=OUT/"intent"/fp.name; write_jsonl(outp, rows); keep(outp)
        except Exception:
            outp=OUT/"intent"/fp.name
            outp.write_text(mask_general(fp.read_text("utf-8",errors="ignore")), "utf-8"); keep(outp)

# FN/FP 彙整（取最新一次 eval 目錄）
ev_dirs = sorted((ROOT/"reports_auto/eval").glob("*/"), key=lambda p:p.stat().st_mtime, reverse=True)
if ev_dirs:
    latest = ev_dirs[0]
    for kind in ("FN","FP"):
        merged = OUT/"intent"/f"{kind}_merged.txt"
        buf=[]
        for txt in sorted(latest.glob(f"{kind}_*.txt")):
            for ln in txt.read_text("utf-8",errors="ignore").splitlines():
                if ln.strip(): buf.append(mask_general(ln.strip()))
        merged.write_text("\n".join(buf), "utf-8"); keep(merged)

# -------- KIE --------
gold = ROOT/"data/kie_eval/gold_merged.jsonl"
if gold.exists() and gold.stat().st_size>0:
    rows=[]
    for ln in gold.read_text("utf-8").splitlines():
        if not ln.strip(): continue
        obj=json.loads(ln); obj["text"]=mask_fixed_len(obj.get("text","")); rows.append(obj)
    outp=OUT/"kie/gold_merged_mask_fixed.jsonl"; write_jsonl(outp, rows); keep(outp)

kiedirs = sorted((ROOT/"reports_auto/kie_eval").glob("*/"), key=lambda p:p.stat().st_mtime, reverse=True)
if kiedirs:
    hp = kiedirs[0]/"hybrid_preds.jsonl"
    if hp.exists():
        rows=[]
        for ln in hp.read_text("utf-8").splitlines():
            if not ln.strip(): continue
            obj=json.loads(ln); obj["text"]=mask_fixed_len(obj.get("text","")); rows.append(obj)
        outp=OUT/"kie/hybrid_preds_mask_fixed.jsonl"; write_jsonl(outp, rows); keep(outp)
    met = kiedirs[0]/"metrics_kie_spans.md"
    if met.exists():
        outp=OUT/"kie/metrics_kie_spans.md"; outp.write_text(met.read_text("utf-8"),"utf-8"); keep(outp)
    um = kiedirs[0]/"unmatched_examples.jsonl"
    if um.exists():
        rows=[]
        for ln in um.read_text("utf-8").splitlines():
            if not ln.strip(): continue
            obj=json.loads(ln); obj["text"]=mask_fixed_len(obj.get("text","")); rows.append(obj)
        outp=OUT/"kie/unmatched_examples_mask_fixed.jsonl"; write_jsonl(outp, rows); keep(outp)

# -------- Spam --------
preds = ROOT/"artifacts_prod/text_predictions_test.tsv"
if preds.exists():
    import csv
    mask_tsv = OUT/"spam/text_predictions_test_masked.tsv"
    with preds.open("r", encoding="utf-8", errors="ignore") as f, mask_tsv.open("w", encoding="utf-8", newline="") as w:
        rd = csv.DictReader(f, delimiter="\t")
        fns = rd.fieldnames or ["id","subject","label_true","prob_spam","pred"]
        wr = csv.DictWriter(w, fieldnames=fns, delimiter="\t"); wr.writeheader()
        for row in rd:
            row["subject"]=mask_general(row.get("subject","")); wr.writerow(row)
    keep(mask_tsv)

for extra in [ROOT/"artifacts_prod/ens_thresholds.json", ROOT/"artifacts_prod/model_meta.json"]:
    if extra.exists():
        outp=OUT/"spam"/extra.name; outp.write_text(extra.read_text("utf-8"),"utf-8"); keep(outp)

# SCORECARD（若有）
sc = sorted((ROOT/"reports_auto/status").glob("SCORECARD_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if sc:
    outp=OUT/"SCORECARD_latest.md"; outp.write_text(sc[0].read_text("utf-8"),"utf-8"); keep(outp)

# 輸出 MANIFEST + 打包
man = OUT/"DATA_MANIFEST.md"
man.write_text("\n".join(MAN)+"\n", "utf-8")
tar_path = ROOT/f"reports_auto/final_dump/final_dump_{NOW}.tar.gz"
with tarfile.open(tar_path.as_posix(), "w:gz") as tar:
    tar.add(OUT.as_posix(), arcname=f"final_dump_{NOW}")

print(f"[OK] final dump dir  => {OUT.as_posix()}")
print(f"[OK] final dump tar  => {tar_path.as_posix()}")
print(f"[OK] manifest        => {man.as_posix()}")
PY

echo ">>> DONE. Latest dump under: ${OUT}"
