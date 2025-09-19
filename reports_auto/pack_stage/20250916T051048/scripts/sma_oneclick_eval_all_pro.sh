#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
STATUS_DIR="reports_auto/status"
mkdir -p "$STATUS_DIR"

echo "[STEP 1/4] Intent 評估（v11c，含自動校準、混淆矩陣、FN/FP匯出）"
bash scripts/sma_intent_rules_focus_v11c.sh

echo "[STEP 2/4] KIE 評估（hybrid v4，SLA維持 HIL）"
bash scripts/sma_oneclick_kie_hybrid_hotfix_v4.sh

echo "[STEP 3/4] Spam 評估（auto-cal v4_fix：AUC / PR-AUC / 最佳門檻）"
# 若要把最佳門檻落盤到 artifacts_prod/ens_thresholds.json，請用：
#   APPLY=1 bash scripts/sma_oneclick_eval_all_pro.sh
bash scripts/sma_oneclick_spam_autocal_hotfix_v4_fix.sh

echo "[STEP 4/4] 產出總結評分表（SCORECARD）"
python - <<'PY'
# -*- coding: utf-8 -*-
import re, time
from pathlib import Path

ROOT = Path(".")
NOW  = time.strftime("%Y%m%dT%H%M%S")
SCORE = ROOT / f"reports_auto/status/SCORECARD_{NOW}.md"

def latest(globs):
    cands=[]
    for g in globs:
        cands += list(ROOT.glob(g))
    cands = [p for p in cands if p.exists() and p.stat().st_size>0]
    return max(cands, key=lambda p:p.stat().st_mtime) if cands else None

def parse_intent(md):
    if not md: return {}
    t = md.read_text("utf-8")
    m_micro = re.search(r"- micro P/R/F1:\s*([0-9.]+)/([0-9.]+)/([0-9.]+)", t)
    m_macro = re.search(r"- macro F1:\s*([0-9.]+)", t)
    return {
        "file": md.as_posix(),
        "micro_tuple": tuple(map(float, m_micro.groups())) if m_micro else None,
        "micro_f1": float(m_micro.group(3)) if m_micro else None,
        "macro_f1": float(m_macro.group(1)) if m_macro else None,
    }

def parse_kie(md):
    if not md: return {}
    t = md.read_text("utf-8")
    s_micro = re.search(r"- strict micro P/R/F1:\s*([0-9.]+)/([0-9.]+)/([0-9.]+)", t)
    s_macro = re.search(r"- strict macro F1:\s*([0-9.]+)", t)
    l_micro = re.search(r"- lenient micro P/R/F1:\s*([0-9.]+)/([0-9.]+)/([0-9.]+)", t)
    return {
        "file": md.as_posix(),
        "strict_micro_tuple": tuple(map(float, s_micro.groups())) if s_micro else None,
        "strict_micro_f1": float(s_micro.group(3)) if s_micro else None,
        "strict_macro_f1": float(s_macro.group(1)) if s_macro else None,
        "lenient_micro_tuple": tuple(map(float, l_micro.groups())) if l_micro else None,
        "lenient_micro_f1": float(l_micro.group(3)) if l_micro else None,
    }

def parse_spam(md):
    if not md: return {}
    t = md.read_text("utf-8")
    m_roc = re.search(r"- ROC-AUC:\s*([0-9.]+)", t)
    m_pr  = re.search(r"- PR-AUC:\s*([0-9.]+)", t)
    best = {}
    if "Best threshold by F1" in t:
        seg = t.split("Best threshold by F1", 1)[1]
        m_th = re.search(r"- threshold:\s*\*\*([0-9.]+)\*\*", seg)
        m_pf = re.search(r"- P/R/F1:\s*\*\*([0-9.]+)/([0-9.]+)/([0-9.]+)\*\*", seg)
        if m_th: best["th"] = float(m_th.group(1))
        if m_pf: best["p"], best["r"], best["f1"] = map(float, m_pf.groups())
    return {
        "file": md.as_posix(),
        "roc_auc": float(m_roc.group(1)) if m_roc else None,
        "pr_auc": float(m_pr.group(1)) if m_pr else None,
        "best": best or None
    }

intent_md = latest([
    "reports_auto/eval/*/metrics_intent_rules_hotfix_v11c.md",
    "reports_auto/eval/*/metrics_intent_rules_hotfix_v11b.md",
    "reports_auto/eval/*/metrics_intent_rules_hotfix_v11.md",
])
kie_md    = latest(["reports_auto/kie_eval/*/metrics_kie_spans.md"])
spam_md   = latest(["reports_auto/eval/*/metrics_spam_autocal_v4.md"])

intent = parse_intent(intent_md)
kie    = parse_kie(kie_md)
spam   = parse_spam(spam_md)

verdicts = {
    "Spam":   "PASS" if (spam.get("roc_auc",0)>=0.98 and spam.get("pr_auc",0)>=0.97 and (spam.get("best",{}).get("f1",0)>=0.94)) else "REVIEW",
    "Intent": "PASS" if (intent.get("micro_f1",0)>=0.73 and intent.get("macro_f1",0)>=0.65) else "PILOT",
    "KIE":    "PASS+HIL(SLA)" if (kie.get("strict_micro_f1",0)>=0.80 and kie.get("lenient_micro_f1",0)>=0.83) else "PILOT",
}

with SCORE.open("w", encoding="utf-8") as w:
    w.write(f"# ONE-CLICK Scorecard ({NOW})\n\n")
    w.write("彙整 Intent / KIE / Spam 的關鍵指標與就緒判定。\n\n")

    w.write("## Intent (rules v11c)\n")
    if intent:
        w.write(f"- report: `{intent['file']}`\n")
        if intent.get("micro_tuple"):
            p,r,f1 = intent["micro_tuple"]
            w.write(f"- micro P/R/F1: **{p:.3f}/{r:.3f}/{f1:.3f}**\n")
        if intent.get("macro_f1") is not None:
            w.write(f"- macro F1: **{intent['macro_f1']:.3f}**\n")
        w.write(f"- verdict: **{verdicts['Intent']}**\n\n")
    else:
        w.write("- report: N/A\n\n")

    w.write("## KIE (hybrid v4)\n")
    if kie:
        w.write(f"- report: `{kie['file']}`\n")
        if kie.get("strict_micro_tuple"):
            p,r,f1 = kie["strict_micro_tuple"]
            w.write(f"- strict micro P/R/F1: **{p:.3f}/{r:.3f}/{f1:.3f}**\n")
        if kie.get("strict_macro_f1") is not None:
            w.write(f"- strict macro F1: **{kie['strict_macro_f1']:.3f}**\n")
        if kie.get("lenient_micro_tuple"):
            p,r,f1 = kie["lenient_micro_tuple"]
            w.write(f"- lenient micro P/R/F1: **{p:.3f}/{r:.3f}/{f1:.3f}**\n")
        w.write(f"- verdict: **{verdicts['KIE']}**（SLA 欄位維持 HIL）\n\n")
    else:
        w.write("- report: N/A\n\n")

    w.write("## Spam (auto-cal v4)\n")
    if spam:
        w.write(f"- report: `{spam['file']}`\n")
        if spam.get("roc_auc") is not None:
            w.write(f"- ROC-AUC: **{spam['roc_auc']:.3f}**\n")
        if spam.get("pr_auc") is not None:
            w.write(f"- PR-AUC: **{spam['pr_auc']:.3f}**\n")
        if spam.get("best"):
            w.write(f"- Best threshold by F1: **{spam['best']['th']:.3f}** ，F1=**{spam['best']['f1']:.3f}**\n")
        w.write(f"- verdict: **{verdicts['Spam']}**\n\n")
    else:
        w.write("- report: N/A\n\n")

print(f"[OK] scorecard -> {SCORE.as_posix()}")
PY

echo ">>> SCORECARD:"
LATEST_SCORECARD="$(ls -t reports_auto/status/SCORECARD_* 2>/dev/null | head -n1 || true)"
if [ -n "$LATEST_SCORECARD" ]; then
  echo "$LATEST_SCORECARD"
  echo "-----"
  sed -n '1,200p' "$LATEST_SCORECARD"
else
  echo "[WARN] 尚未生成 SCORECARD_* 檔案"
fi

echo "[DONE] oneclick eval finished."
