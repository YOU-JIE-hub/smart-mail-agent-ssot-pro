#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT" || exit 2
[[ -d .venv ]] || python3 -m venv .venv; . .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}" TOKENIZERS_PARALLELISM=false
mkdir -p reports_auto/{logs,diagnostics}
TS="$(date +%Y%m%dT%H%M%S)"; LOG="reports_auto/logs/align_probe_${TS}.log"
ln -sf "$(basename "$LOG")" reports_auto/logs/latest.log || true
exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1
trap 'ec=$?; tail -n 200 "$LOG" > "reports_auto/diagnostics/LAST_TAIL_${TS}.log"; exit $ec' ERR
python - <<'PY'
import json,re,unicodedata,pathlib
def load(p):
    out=[]; pth=pathlib.Path(p)
    if not pth.exists(): return out
    with open(p,encoding="utf-8",errors="ignore") as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out
def norm(s):
    if s is None: return ""
    s=unicodedata.normalize("NFKC",str(s)).replace("\u3000"," ").lower()
    return re.sub(r"\s+"," ",s).strip()
def extract(o):
    parts=[]
    for k in ("subject","title","content","body","text","plain","raw_text","snippet","summary","description","text_norm","body_norm"):
        v=o.get(k); 
        if isinstance(v,str): parts.append(v)
    for kk in ("src","source","email","payload","data"):
        v=o.get(kk)
        if isinstance(v,dict):
            for k in ("subject","title","content","body","text","plain","raw_text","snippet","summary","description","text_norm","body_norm"):
                vv=v.get(k)
                if isinstance(vv,str): parts.append(vv)
    return norm("\n".join(parts))
def ngrams(s,n=3): return {s[i:i+n] for i in range(max(0,len(s)-n+1))} if s else set()
def jacc(a,b):
    if not a or not b: return 0.0
    A,B=ngrams(a),ngrams(b); u=len(A|B); return (len(A&B)/u) if u else 0.0
pred=load("reports_auto/predict_all.jsonl"); pt=[extract(o) for o in pred]
gold=load("data/intent/test_labeled.jsonl"); gt=[extract(o) for o in gold]
def best(G,P):
    out=[]
    for t in G:
        best=0.0
        for p in P:
            s=jacc(t,p)
            if s>best: best=s
        out.append(best)
    return out
bs=best(gt,pt) if gt and pt else []
cov=[0.95,0.90,0.85,0.80,0.70]
from datetime import datetime
out=pathlib.Path("reports_auto/diagnostics")/("ALIGN_ZERO_MATCH_CAUSE_"+datetime.now().strftime("%Y%m%dT%H%M%S")+".md")
with open(out,"w",encoding="utf-8") as f:
    f.write("# ALIGN zero-match diagnosis\n\n")
    f.write(f"- pred: {len(pred)}; gold_intent: {len(gold)}\n")
    f.write(f"- pred empty: {sum(1 for t in pt if not t)}/{len(pt)}\n")
    f.write(f"- gold empty: {sum(1 for t in gt if not t)}/{len(gt)}\n\n")
    if bs:
        f.write("## best-sim coverage\n")
        for th in cov:
            f.write(f"- ≥{th}: {sum(1 for x in bs if x>=th)/len(bs):.4f}\n")
print(f"[WRITE] {out}")
PY

DIAG="reports_auto/diagnostics"
if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$PWD/$DIAG")" || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$DIAG" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$DIAG" || true
fi
