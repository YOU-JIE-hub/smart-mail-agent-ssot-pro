#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
WORKDIR="reports_auto/intent_autofix/${TS}"
mkdir -p "$WORKDIR"

DATA_DIR="data/intent_eval"
ORIG="${DATA_DIR}/dataset.jsonl"
CLEAN="${DATA_DIR}/dataset.cleaned.jsonl"

if [ ! -f "$CLEAN" ]; then
  echo "[FATAL] 找不到 ${CLEAN}，請先跑清洗腳本"; exit 2
fi
if [ ! -f "$ORIG" ]; then
  echo "[FATAL] 找不到 ${ORIG}"; exit 2
fi

# 保存「跑前」最近一份 v7 指標（若無則忽略）
BEFORE_MD="$(ls -t reports_auto/eval/*/metrics_intent_rules_hotfix_v7.md 2>/dev/null | head -n1 || true)"

# 臨時覆蓋 dataset.jsonl 用 cleaned 執行 v7
cp -f "$ORIG" "${WORKDIR}/dataset.orig.backup.jsonl"
cp -f "$CLEAN" "$ORIG"
echo "[INFO] 使用 cleaned 資料集臨時覆蓋後執行 v7…"
bash scripts/sma_oneclick_intent_rules_hotfix_v7.sh

# 取「跑後」最近一份 v7 指標
AFTER_MD="$(ls -t reports_auto/eval/*/metrics_intent_rules_hotfix_v7.md | head -n1)"
echo "[OK] v7(after) => ${AFTER_MD}"

# 還原或永久採用
if [ "${APPLY:-0}" = "1" ]; then
  echo "[APPLY] 保留 cleaned 為正式 dataset.jsonl"
else
  cp -f "${WORKDIR}/dataset.orig.backup.jsonl" "$ORIG"
  echo "[OK] 已還原原始 dataset.jsonl"
fi

# 產生差異報告
python - <<'PY'
# -*- coding: utf-8 -*-
import re, json
from pathlib import Path

def parse_md(p: Path):
    txt = p.read_text('utf-8')
    out = {"micro": None, "macro": None, "labels": {}}
    m = re.search(r"micro P/R/F1:\s*([0-9.]+)/([0-9.]+)/([0-9.]+)", txt)
    if m:
        out["micro"] = tuple(float(x) for x in m.groups())
    m = re.search(r"macro F1:\s*([0-9.]+)", txt)
    if m:
        out["macro"] = float(m.group(1))
    # 取第一個 label 表
    tbl = re.search(r"\|label\|P\|R\|F1\|TP\|FP\|FN\|\n\|[-|:]+\|\n(?P<body>(?:\|.*\|\n)+)", txt)
    if tbl:
        for line in tbl.group("body").strip().splitlines():
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 4:
                label, P, R, F1 = cols[:4]
                try:
                    out["labels"][label] = tuple(map(float, (P, R, F1)))
                except:
                    pass
    return out

ROOT = Path(".")
WORKDIRS = sorted((ROOT/"reports_auto/intent_autofix").glob("*"))
WORKDIR = WORKDIRS[-1] if WORKDIRS else ROOT

# 找到最新兩份 v7 指標（跑前/跑後）
all_v7 = sorted((ROOT/"reports_auto/eval").glob("*/metrics_intent_rules_hotfix_v7.md"), key=lambda p:p.stat().st_mtime)
after = all_v7[-1] if all_v7 else None
before = all_v7[-2] if len(all_v7)>=2 else None

report = ROOT / WORKDIR / "intent_v7_compare.md"
with report.open("w", encoding="utf-8") as w:
    w.write("# Intent v7: cleaned 資料集 重新評測差異\n\n")
    if not after:
        w.write("[FATAL] 找不到 v7 指標（after）\n")
    else:
        w.write(f"- after : {after.as_posix()}\n")
    if before:
        w.write(f"- before: {before.as_posix()}\n\n")
    else:
        w.write("- before: (無可比較的舊檔)\n\n")

    if after:
        aft = parse_md(after)
        if before:
            bef = parse_md(before)
            # 總覽差異
            if aft["micro"] and bef["micro"]:
                dm = [aft["micro"][i]-bef["micro"][i] for i in range(3)]
                w.write(f"## Micro P/R/F1 變化\n- before: {bef['micro'][0]:.3f}/{bef['micro'][1]:.3f}/{bef['micro'][2]:.3f}\n")
                w.write(f"- after : {aft['micro'][0]:.3f}/{aft['micro'][1]:.3f}/{aft['micro'][2]:.3f}\n")
                w.write(f"- delta : {dm[0]:+.3f}/{dm[1]:+.3f}/{dm[2]:+.3f}\n\n")
            if aft["macro"] is not None and bef["macro"] is not None:
                w.write(f"## Macro F1 變化\n- before: {bef['macro']:.3f}\n- after : {aft['macro']:.3f}\n- delta : {aft['macro']-bef['macro']:+.3f}\n\n")

            # 標籤層級差異
            w.write("## Per-label F1 變化\n\n|label|P_before|R_before|F1_before|P_after|R_after|F1_after|ΔF1|\n|---|---:|---:|---:|---:|---:|---:|---:|\n")
            labels = sorted(set(bef["labels"].keys()) | set(aft["labels"].keys()))
            for lb in labels:
                pb, rb, fb = bef["labels"].get(lb, (float('nan'),)*3)
                pa, ra, fa = aft["labels"].get(lb, (float('nan'),)*3)
                df = (fa - fb) if (not any(map(lambda x: x!=x, [fa, fb]))) else float('nan')
                def f(x): return ("-" if x!=x else f"{x:.3f}")  # nan -> "-"
                w.write(f"|{lb}|{f(pb)}|{f(rb)}|{f(fb)}|{f(pa)}|{f(ra)}|{f(fa)}|{f(df)}|\n")
        else:
            w.write("_沒有 before 指標可比較，已僅輸出 after 概況。_\n")

print(f"[OK] diff report -> {report.as_posix()}")
PY

# 最後把重點路徑列出
echo ">>> Intent cleaned v7 差異報告："
ls -1 "${WORKDIR}/intent_v7_compare.md" 2>/dev/null || true
echo ">>> 如要永久採用 cleaned 請重跑： APPLY=1 bash scripts/sma_intent_rules_eval_on_cleaned_v7.sh"
