#!/usr/bin/env python3
# 檔案位置：.sma_tools/summary_report.py
# 模組用途：彙整三模型報告到 reports_auto/SUMMARY.md
from __future__ import annotations
from pathlib import Path

SPAM = Path("reports_auto/spam_cn_eval.txt")
INTB = Path("reports_auto/intent_eval_exact.txt")
KIE1 = Path("reports_auto/kie_eval.txt")
KIE2 = Path("reports_auto/kie_eval_per_label.tsv")

out = Path("reports_auto/SUMMARY.md")
out.parent.mkdir(parents=True, exist_ok=True)

lines = []
lines.append("# 三模型評測摘要")
lines.append("")
lines.append("## 資產路徑")
lines.append("- INTENT 權重：`artifacts/intent_pro_cal.pkl`")
lines.append("- INTENT 標準化權重：`artifacts/intent_pro_cal_fixed.pkl`（若 OVERWRITE=1 則原檔已被覆蓋）")
lines.append("- SPAM 權重：`artifacts_prod/model_pipeline.pkl`")
lines.append("- KIE 權重資料夾：`artifacts/releases/kie_xlmr/current/`")
lines.append("")
if SPAM.exists():
    lines.append("## SPAM 指標（節選）")
    lines.extend(["```", SPAM.read_text(encoding="utf-8").strip(), "```", ""])
if INTB.exists():
    lines.append("## INTENT Base 指標（external_realistic_test.clean.jsonl）")
    lines.extend(["```", INTB.read_text(encoding="utf-8").strip(), "```", ""])
if KIE1.exists():
    lines.append("## KIE 指標（strict-span）")
    lines.extend(["```", KIE1.read_text(encoding="utf-8").strip(), "```", ""])
if KIE2.exists():
    lines.append("## KIE 每標籤指標")
    head = "\n".join(KIE2.read_text(encoding="utf-8").splitlines()[:12])
    lines.extend(["```", head, "```", ""])
out.write_text("\n".join(lines), encoding="utf-8")
print(f"[OK] wrote {out}")
