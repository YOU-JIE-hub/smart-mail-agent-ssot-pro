#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/kie_eval_boost/${TS}"
mkdir -p "$OUT"

python - <<'PY'
# -*- coding: utf-8 -*-
import re, json, time, math
from pathlib import Path
from collections import defaultdict

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
def read_jsonl(p):
    out=[]; 
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if ln: out.append(json.loads(ln))
    return out

# 拿最新 hybrid 預測與 gold
kie_dirs=sorted((ROOT/"reports_auto/kie_eval").glob("*/"), key=lambda p:p.stat().st_mtime, reverse=True)
assert kie_dirs, "no kie reports"
pred_p=kie_dirs[0]/"hybrid_preds.jsonl"
met_p =kie_dirs[0]/"metrics_kie_spans.md"
gold_p=ROOT/"data/kie_eval/gold_merged.jsonl"
pred=read_jsonl(pred_p); gold=read_jsonl(gold_p)

def add_sla_spans(rec):
    txt=rec.get("text","")
    spans=rec.get("spans") or []
    has_sla=any(s.get("label")=="sla" for s in spans)
    if has_sla: return rec
    # 簡單抓 SLA 關鍵詞或時間區段
    patterns=[
        r"(?:(?:SLA)|服務等級|回覆時間|回覆時段|支援時段|客服時間|on[- ]call|support hours|response time|RTO|RPO)",
        r"\b(?:[01]?\d|2[0-3]):[0-5]\d\s*-\s*(?:[01]?\d|2[0-3]):[0-5]\d\b",
    ]
    m=None
    for pat in patterns:
        m=re.search(pat, txt, flags=re.I)
        if m: break
    if m:
        spans.append({"start": m.start(), "end": m.end(), "label":"sla", "score":0.60, "src":"postboost", "needs_review": True})
        rec["spans"]=spans
    return rec

boost=[add_sla_spans(dict(r)) for r in pred]

# 評分（strict = IoU 1.0, lenient = IoU 0.5）
def iou(a,b):
    s=max(a[0],b[0]); e=min(a[1],b[1])
    inter=max(0,e-s); uni=(a[1]-a[0])+(b[1]-b[0])-inter
    return (inter/uni) if uni>0 else 0.0

def score(gold, pred, thr):
    labels=set(["amount","date_time","env","sla"])
    agg={l:{"TP":0,"FP":0,"FN":0} for l in labels}
    for g,p in zip(gold, pred):
        gsp=[(s["start"],s["end"],s["label"]) for s in (g.get("spans") or [])]
        psp=[(s["start"],s["end"],s["label"]) for s in (p.get("spans") or [])]
        # 按 label 分組 greedy match
        for lb in labels:
            G=[x for x in gsp if x[2]==lb]
            P=[x for x in psp if x[2]==lb]
            used=set()
            for gi,gs in enumerate(G):
                # 找到 iou 最大且 >=thr 的預測
                best=-1; bestj=-1
                for j,ps in enumerate(P):
                    if j in used: continue
                    v=iou((gs[0],gs[1]), (ps[0],ps[1]))
                    if v>=thr and v>best:
                        best=v; bestj=j
                if bestj>=0:
                    agg[lb]["TP"]+=1
                    used.add(bestj)
                else:
                    agg[lb]["FN"]+=1
            # 剩下未匹配的都是 FP
            agg[lb]["FP"]+= max(0, len(P)-len(used))
    # 產出 P/R/F1
    def prf(TP,FP,FN):
        P= TP/(TP+FP) if (TP+FP)>0 else 0.0
        R= TP/(TP+FN) if (TP+FN)>0 else 0.0
        F= (2*P*R/(P+R)) if (P+R)>0 else 0.0
        return P,R,F
    rows=[]
    microTP=microFP=microFN=0
    for lb in sorted(agg.keys()):
        TP,FP,FN=agg[lb]["TP"],agg[lb]["FP"],agg[lb]["FN"]
        p,r,f=prf(TP,FP,FN); rows.append((lb,p,r,f,TP,FP,FN))
        microTP+=TP; microFP+=FP; microFN+=FN
    mp=sum(r[3] for r in rows)/len(rows) if rows else 0.0
    P,R,F=prf(microTP,microFP,microFN)
    return {"rows":rows, "micro":(P,R,F), "macroF1":mp}

strict=score(gold, boost, 1.0)
lenient=score(gold, boost, 0.5)

OUT=ROOT/f"reports_auto/kie_eval_boost/{NOW}"
OUT.mkdir(parents=True, exist_ok=True)
(OUT/"hybrid_preds_boost.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in boost), "utf-8")

def to_row(r): 
    lb,p,r_,f,tp,fp,fn=r
    return f"|{lb}|{p:.3f}|{r_:.3f}|{f:.3f}|{tp}|{fp}|{fn}|"

md = [
"# KIE span metrics (post-boost SLA)",
f"- base_pred: {pred_p.as_posix()}",
f"- gold_file: {gold_p.as_posix()}",
"",
"## strict (IoU=1.0)",
f"- micro P/R/F1: {strict['micro'][0]:.3f}/{strict['micro'][1]:.3f}/{strict['micro'][2]:.3f}",
f"- macro F1: {strict['macroF1']:.3f}",
"|label|P|R|F1|TP|FP|FN|","|---|---:|---:|---:|---:|---:|---:|",
*([to_row(r) for r in strict["rows"]]),
"",
"## lenient (IoU≥0.50)",
f"- micro P/R/F1: {lenient['micro'][0]:.3f}/{lenient['micro'][1]:.3f}/{lenient['micro'][2]:.3f}",
f"- macro F1: {lenient['macroF1']:.3f}",
"|label|P|R|F1|TP|FP|FN|","|---|---:|---:|---:|---:|---:|---:|",
*([to_row(r) for r in lenient["rows"]]),
]
(OUT/"metrics_kie_spans_postboost.md").write_text("\n".join(md), "utf-8")
print(f"[OK] boosted preds  -> {(OUT/'hybrid_preds_boost.jsonl').as_posix()}")
print(f"[OK] boosted metric -> {(OUT/'metrics_kie_spans_postboost.md').as_posix()}")
PY
