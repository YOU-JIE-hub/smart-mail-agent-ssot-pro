#!/usr/bin/env python3
import os, re, subprocess, datetime, pathlib, json
from collections import Counter

R = pathlib.Path("reports_auto")
B_EVAL = R / "external_eval_manual.txt"
P_EVAL = R / "external_eval_manual_pro.txt"
FB_EVAL = R / "external_fallback_eval.txt"
MODEL_CARD = R / "MODEL_CARD.md"
REL_NOTES  = R / "RELEASE_NOTES.md"

def read_text(p): return pathlib.Path(p).read_text(encoding="utf-8") if pathlib.Path(p).exists() else ""
def parse_accuracy(txt):
    m = re.search(r'accuracy\s+([0-9.]+)', txt) or re.search(r'accuracy\s*=\s*([0-9.]+)', txt)
    return float(m.group(1)) if m else None
def top_error_pairs(tsv, topn=8):
    if not pathlib.Path(tsv).exists(): return []
    rows = [l.split("\t") for l in read_text(tsv).splitlines()[1:] if l.strip()]
    c = Counter()
    for r in rows:
        if len(r)>=4 and r[2]!=r[3]:
            c[f"{r[2]}->{r[3]}"] += 1
    return c.most_common(topn)
def git_shortrev():
    try: return subprocess.check_output(["git","rev-parse","--short","HEAD"], text=True).strip()
    except Exception: return "unknown"
def write_model_card():
    b_txt, p_txt, fb_txt = read_text(B_EVAL), read_text(P_EVAL), read_text(FB_EVAL)
    acc_b, acc_p, acc_fb = parse_accuracy(b_txt), parse_accuracy(p_txt), parse_accuracy(fb_txt)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rev = git_shortrev()
    pairs = top_error_pairs("reports_auto/external_errors_pro.tsv", topn=8)
    md = []
    md += [f"# INTENT Model Card\n", f"- **Repo rev**: `{rev}`\n- **Generated**: {now}\n"]
    md += ["## Task & Data\n- 6 intents (biz_quote / complaint / other / policy_qa / profile_update / tech_support)\n- Train: `data/intent/i_20250901_merged.jsonl` (n=354)\n- Test:  `data/intent/external_realistic_test.clean.jsonl` (n=120, 6×20)\n"]
    md += ["## Method\n- Features: TF-IDF(word 1–2) + TF-IDF(char 3–5) + DictFeaturizer\n- Classifier: LinearSVC(class_weight='balanced') + CalibratedClassifierCV(sigmoid, cv=3)\n- Post-process: fallback(threshold/margin) + rules-guard(only tech_support)\n"]
    md += ["## Evaluation\n| Setting | Accuracy |\n|---|---|\n"]
    if acc_b is not None:  md += [f"| Baseline | {acc_b:.3f} |\n"]
    if acc_p is not None:  md += [f"| Pro (calibrated) | {acc_p:.3f} |\n"]
    if acc_fb is not None: md += [f"| Pro + Fallback | {acc_fb:.3f} |\n"]
    if pairs:
        md += ["\n**Top error transitions (Pro):**\n"]
        for k,v in pairs: md += [f"- {k}: {v}\n"]
    md += ["\n## Repro Commands\n```bash\nSEED=42 .sma_tools/oneclick_train_eval_pro.sh downloads/external_realistic_test.jsonl\n.sma_tools/demo_fallback.sh 0.52 0.10\n```\n"]
    md += ["\n## Known Limitations\n- “other” vs “tech_support” 需規則護欄或更多標註\n- 混語/術語需要擴充詞表與資料\n"]
    MODEL_CARD.write_text("".join(md), encoding="utf-8")
    return acc_b, acc_p, acc_fb

def write_release_notes(acc_b, acc_p, acc_fb):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rev = git_shortrev()
    delta = (acc_p - acc_b) if (acc_p is not None and acc_b is not None) else None
    lines = [f"# Release Notes — INTENT\n- **Rev**: `{rev}`  \n- **Date**: {now}\n","## Highlights\n"]
    if acc_p is not None:
        lines += [f"- Pro calibrated pipeline: accuracy {acc_p:.3f}"]
        if delta is not None: lines += [f" (Δ vs baseline: {delta:+.3f})"]
        lines += ["\n"]
    if acc_fb is not None: lines += [f"- With fallback: accuracy {acc_fb:.3f}\n"]
    lines += ["## Changes\n- Fix: f-string 反斜線輸出\n- Fix: sklearn CalibratedClassifierCV 參數改名\n- Compat: joblib `__main__.DictFeaturizer`\n- Tooling: 一鍵訓練/驗收、fallback 掃描、產卡\n"]
    REL_NOTES.write_text("".join(lines), encoding="utf-8")

def main():
    R.mkdir(parents=True, exist_ok=True)
    acc_b, acc_p, acc_fb = write_model_card()
    write_release_notes(acc_b, acc_p, acc_fb)
    print(f"[OK] wrote: {MODEL_CARD} , {REL_NOTES}")

if __name__ == "__main__":
    main()
