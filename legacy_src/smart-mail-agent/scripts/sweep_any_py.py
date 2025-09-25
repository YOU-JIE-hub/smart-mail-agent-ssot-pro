#!/usr/bin/env python3
import subprocess, re, json, os, argparse
from pathlib import Path

RE_MACRO = re.compile(r"macro_f1=([0-9.]+)")
RE_HAM   = re.compile(r"ham\s+P/R/F1\s*=\s*([0-9.]+)/([0-9.]+)/([0-9.]+)", re.I)
RE_SPAM  = re.compile(r"spam\s+P/R/F1\s*=\s*([0-9.]+)/([0-9.]+)/([0-9.]+)", re.I)

ap=argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--artifacts", required=True)
ap.add_argument("--out_tsv", required=True)
ap.add_argument("--target_recall", type=float, default=0.95)
a=ap.parse_args()

DATA=a.data
ART=Path(a.artifacts)
MODEL=str(ART/"spam_rules_lr.pkl")
THJ  =ART/"spam_thresholds.json"
OUT  =Path(a.out_tsv)
assert Path(MODEL).exists(), "model not found in artifacts"

def eval_at(thr: float):
    THJ.write_text(json.dumps({"threshold": round(thr,2)}))
    p=subprocess.run(
        ["python","scripts/run_spam_eval.py",
         "--data", DATA, "--rules", ".sma_tools/spam_rules.yml",
         "--model", MODEL, "--thresholds", str(THJ)],
        capture_output=True, text=True, check=False, env={**os.environ, "PYTHONPATH":"src"})
    out=p.stdout
    m=RE_MACRO.search(out); macro=float(m.group(1)) if m else float("nan")
    mh=RE_HAM.search(out);  ms=RE_SPAM.search(out)
    hP,hR,hF=(map(float,mh.groups()) if mh else (float("nan"),)*3)
    sP,sR,sF=(map(float,ms.groups()) if ms else (float("nan"),)*3)
    return {"thr":round(thr,2),"macroF1":macro,"hamP":hP,"hamR":hR,"hamF1":hF,"spamP":sP,"spamR":sR,"spamF1":sF}

rows=[eval_at(round(i/100,2)) for i in range(0,100)]  # 0.00〜0.99

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w",encoding="utf-8") as w:
    w.write("thr\tmacroF1\thamP\thamR\thamF1\tspamP\tspamR\tspamF1\n")
    for r in rows:
        w.write(f'{r["thr"]}\t{r["macroF1"]}\t{r["hamP"]}\t{r["hamR"]}\t{r["hamF1"]}\t{r["spamP"]}\t{r["spamR"]}\t{r["spamF1"]}\n')

# 選門檻：優先 spamR≥target；否則取 spamR 最大（再看 macroF1）
ok=[r for r in rows if r["spamR"]>=a.target_recall]
if ok:
    pick=max(ok, key=lambda r:(r["macroF1"], -abs(r["thr"]-0.28)))
    reason=f"spamR>={a.target_recall} & macroF1 max"
else:
    pick=max(rows, key=lambda r:(r["spamR"], r["macroF1"]))
    reason=f"no thr reaches spamR>={a.target_recall}; pick by spamR then macroF1"

THJ.write_text(json.dumps({"threshold": pick["thr"]}))
print(f"[SELECT] thr={pick['thr']} ({reason})")
print("[TOP macroF1]")
for r in sorted(rows,key=lambda r:r["macroF1"],reverse=True)[:8]:
    print(f"  thr={r['thr']:.2f} macroF1={r['macroF1']:.4f}  hamF1={r['hamF1']:.3f} spamR={r['spamR']:.3f} spamF1={r['spamF1']:.3f}")
print("[TOP spamR]")
for r in sorted(rows,key=lambda r:(r["spamR"],r["macroF1"]),reverse=True)[:5]:
    print(f"  thr={r['thr']:.2f} spamR={r['spamR']:.3f} macroF1={r['macroF1']:.4f} hamF1={r['hamF1']:.3f} spamF1={r['spamF1']:.3f}")
print(f"[WRITE] {OUT}")
