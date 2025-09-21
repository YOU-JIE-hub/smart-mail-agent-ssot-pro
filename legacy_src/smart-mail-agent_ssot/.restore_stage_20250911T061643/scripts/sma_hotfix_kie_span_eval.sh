#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
export TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports_auto/kie_eval/"$TS" data/kie_eval reports_auto/status

python - <<'PY'
import json, os, re, time
from pathlib import Path

root=Path(".")
# 1) 收集可能的金標檔
search_dirs=[root/"artifacts_inbox", root/"data/staged_project", root]
want_names={"gold_for_train.jsonl","label_queue.jsonl","silver.jsonl","silver_base.jsonl",
            "silver_val.jsonl","test.jsonl","test.demo.jsonl","test_real.jsonl",
            "train.jsonl","val.jsonl"}
cands=[]
for base in search_dirs:
    if not base.exists(): continue
    for dp,_,fs in os.walk(base):
        for n in fs:
            if n in want_names or (n.startswith("silver") and n.endswith(".jsonl")) or (n.startswith("test") and n.endswith(".jsonl")):
                p=Path(dp)/n
                if p.stat().st_size>0: cands.append(p)

def load_jsonl(p):
    out=[]
    with p.open("r",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            line=line.strip()
            if not line: continue
            try:
                obj=json.loads(line)
            except Exception:
                continue
            if isinstance(obj,dict) and "text" in obj and "spans" in obj:
                out.append(obj)
    return out

def norm_spans(spans, text):
    ok=[]
    for s in spans:
        try:
            a=int(s["start"]); b=int(s["end"]); lab=str(s["label"])
        except Exception:
            continue
        if a<0 or b<=a or b>len(text): continue
        ok.append((a,b,lab))
    return sorted(set(ok))

all_rows=[]
for p in cands: all_rows += load_jsonl(p)

# 去重：以 (text, spans_set) 作 key
uniq={}
for r in all_rows:
    txt=r.get("text","")
    sp = norm_spans(r.get("spans",[]), txt)
    uniq[(txt,tuple(sp))] = {"text":txt,"spans":[{"start":a,"end":b,"label":lab} for a,b,lab in sp]}
gold=list(uniq.values())

out_gold = root/"data/kie_eval/gold_merged.jsonl"
out_gold.parent.mkdir(parents=True,exist_ok=True)
with out_gold.open("w",encoding="utf-8") as f:
    for r in gold: f.write(json.dumps(r,ensure_ascii=False)+"\n")

# 2) 找預測檔；找不到就做 regex baseline
pred_files=[]
for base in [root/"artifacts_inbox", root/"data/staged_project", root]:
    if base.exists(): pred_files += list(base.rglob("kie_pred*.jsonl"))

def regex_predict(text):
    spans=[]
    # 金額
    for m in re.finditer(r'(?:NT\\$|NTD|新台幣)\\s?\\$?[\\d,]+(?:\\.\\d+)?', text):
        spans.append({"start":m.start(),"end":m.end(),"label":"amount"})
    # 日期
    for m in re.finditer(r'(?:(?:20\\d{2}[/-](?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\\d|3[01]))|(?:\\b(?:[01]?\\d)[/-](?:[0-3]?\\d)\\b))', text):
        spans.append({"start":m.start(),"end":m.end(),"label":"date_time"})
    # 環境
    for m in re.finditer(r'\\b(prod(?:uction)?|staging|uat|sit|preprod|dev(?:elopment)?)\\b', text, flags=re.I):
        spans.append({"start":m.start(),"end":m.end(),"label":"env"})
    return spans

pred_rows=[]
for p in pred_files: pred_rows += load_jsonl(p)
if pred_rows:
    baseline="model"
else:
    baseline="regex"
    pred_rows=[{"text":r["text"], "spans": regex_predict(r["text"])} for r in gold]

# 3) 計分（strict span match，逐 label）
def prf(tp,fp,fn):
    p = tp/(tp+fp) if (tp+fp)>0 else 0.0
    r = tp/(tp+fn) if (tp+fn)>0 else 0.0
    f1= 2*p*r/(p+r) if (p+r)>0 else 0.0
    return p,r,f1

pred_map={r["text"]: norm_spans(r.get("spans",[]), r.get("text","")) for r in pred_rows}
labels=set()
for r in gold: labels.update([s["label"] for s in r["spans"]])
labels=sorted(labels)

from collections import defaultdict
agg=defaultdict(lambda: {"tp":0,"fp":0,"fn":0})
for r in gold:
    txt=r["text"]
    g = norm_spans(r["spans"], txt)
    p = pred_map.get(txt, [])
    for lab in labels:
        G={t for t in g if t[2]==lab}
        P={t for t in p if t[2]==lab}
        agg[lab]["tp"] += len(G & P)
        agg[lab]["fp"] += len(P - G)
        agg[lab]["fn"] += len(G - P)

rows=[]; macro=[]
for lab in labels:
    tp,fp,fn = agg[lab]["tp"], agg[lab]["fp"], agg[lab]["fn"]
    p,r,f1 = prf(tp,fp,fn)
    rows.append((lab,p,r,f1,tp,fp,fn)); macro.append(f1)
macro_f1 = sum(macro)/len(macro) if macro else 0.0

micro_tp=sum(v["tp"] for v in agg.values())
micro_fp=sum(v["fp"] for v in agg.values())
micro_fn=sum(v["fn"] for v in agg.values())
micro_p,micro_r,micro_f1 = prf(micro_tp,micro_fp,micro_fn)

ts=os.environ.get("TS", time.strftime("%Y%m%dT%H%M%S"))
out_dir=root/f"reports_auto/kie_eval/{ts}"
out_dir.mkdir(parents=True,exist_ok=True)

md=[]
md.append(f"# KIE span metrics ({'model preds' if baseline=='model' else 'regex baseline'})")
md.append(f"- gold_files: {len(cands)} merged={out_gold}")
md.append(f"- pred_source: {baseline}")
md.append(f"- micro P/R/F1: {micro_p:.3f}/{micro_r:.3f}/{micro_f1:.3f}")
md.append(f"- macro F1 (strict): {macro_f1:.3f}")
md.append("")
md.append("|label|P|R|F1|TP|FP|FN|")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for lab,p,r,f1,tp,fp,fn in rows:
    md.append(f"|{lab}|{p:.3f}|{r:.3f}|{f1:.3f}|{tp}|{fp}|{fn}|")
(out_dir/"metrics_kie_spans.md").write_text("\n".join(md),encoding="utf-8")

# 4) 附到最新 ONECLICK
status_dir=root/"reports_auto/status"
lst=sorted(status_dir.glob("ONECLICK_*"), key=lambda p: p.stat().st_mtime, reverse=True)
if lst:
    with open(lst[0],"a",encoding="utf-8") as f:
        f.write("\n\n## KIE span metrics (hotfix)\n")
        f.write("\n".join(md)+"\n")

print("[OK] wrote", out_dir/"metrics_kie_spans.md")
PY

echo "[DONE] KIE spans hotfix done"
