#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"
OUT_DIR="reports_auto/kie_eval/$TS"
mkdir -p "$OUT_DIR" data/kie_eval reports_auto/status

python - <<'PY'
import json, os, re, time, sys, glob
from pathlib import Path

root=Path(".")
min_conf=float(os.getenv("KIE_MIN_CONF", "0.15"))  # 可用環境變數調
iou_th=float(os.getenv("KIE_IOU", "0.5"))

# -------- 1) 準備 gold --------
gold_merged = root/"data/kie_eval/gold_merged.jsonl"
if not gold_merged.exists() or gold_merged.stat().st_size==0:
    want={"gold_for_train.jsonl","label_queue.jsonl","silver.jsonl","silver_base.jsonl",
          "silver_val.jsonl","test.jsonl","test.demo.jsonl","test_real.jsonl",
          "train.jsonl","val.jsonl"}
    search_dirs=[root/"artifacts_inbox", root/"data/staged_project", root]
    seen=set(); rows=[]
    for base in search_dirs:
        if not base.exists(): continue
        for dp,_,fs in os.walk(base):
            for n in fs:
                if (n in want or (n.startswith("silver") and n.endswith(".jsonl")) or (n.startswith("test") and n.endswith(".jsonl"))):
                    p=Path(dp)/n
                    try:
                        for line in p.read_text("utf-8").splitlines():
                            if not line.strip(): continue
                            r=json.loads(line)
                            t=r.get("text") or r.get("body") or r.get("subject") or ""
                            # 去重用 text 做近似鍵
                            key=(t.strip(), json.dumps(sorted([(s.get("start"),s.get("end"),s.get("label")) for s in r.get("spans",[]) if s], key=lambda x:(x[0],x[1],x[2]))))
                            if key in seen: continue
                            seen.add(key)
                            rows.append({"text":t, "spans":[{"start":int(s["start"]), "end":int(s["end"]), "label":str(s["label"])} for s in r.get("spans",[]) if "start" in s and "end" in s and "label" in s]})
                    except Exception: pass
    gold_merged.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), "utf-8")

gold=[]
for line in gold_merged.read_text("utf-8").splitlines():
    if not line.strip(): continue
    r=json.loads(line); t=r.get("text") or r.get("body") or r.get("subject") or ""
    spans=[{"start":int(s["start"]), "end":int(s["end"]), "label":str(s["label"])} for s in r.get("spans",[]) if {"start","end","label"}<=set(s)]
    gold.append({"text":t, "spans":spans})

# -------- 2) 收集 preds（model）--------
def score_of(s):
    for k in ("score","prob","confidence","conf"):
        if isinstance(s, dict) and k in s:
            try: return float(s[k])
            except: pass
    return None

pred_files=[]
for base in (root/"artifacts_inbox", root/"data/staged_project", root):
    pred_files += [Path(p) for p in glob.glob(str(base/"**/kie_pred*.jsonl"), recursive=True)]
pred_files = sorted({p for p in pred_files if p.exists()}, key=lambda p:p.stat().st_mtime, reverse=True)

pred_map={}  # text -> spans list
for pf in pred_files:
    try:
        for line in pf.read_text("utf-8").splitlines():
            if not line.strip(): continue
            r=json.loads(line)
            t=r.get("text") or r.get("body") or r.get("subject") or ""
            out=[]
            for s in r.get("spans",[]) or []:
                if not {"start","end","label"}<=set(s): continue
                sc=score_of(s)
                if sc is None or sc >= min_conf:
                    out.append({"start":int(s["start"]), "end":int(s["end"]), "label":str(s["label"])})
            # 只保留過濾後非空的
            pred_map.setdefault(t, [])
            pred_map[t].extend(out)
    except Exception:
        pass

pred_count=sum(len(v) for v in pred_map.values())

# -------- 3) 評分（strict & lenient）--------
def iou(a,b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return (inter/union) if union>0 else 0.0

def eval_mode(mode="strict"):
    from collections import defaultdict
    TP=defaultdict(int); FP=defaultdict(int); FN=defaultdict(int)
    labels=set()
    for ex in gold:
        t=ex["text"]
        g=ex["spans"]; p=list(pred_map.get(t, []))
        matched=[False]*len(g)
        used=[False]*len(p)
        for j,pp in enumerate(p):
            best=-1; best_i=-1
            for i,gg in enumerate(g):
                if gg["label"]!=pp["label"] or matched[i]: continue
                ok=False
                if mode=="strict":
                    ok = (pp["start"]==gg["start"] and pp["end"]==gg["end"])
                else:
                    ok = (iou((pp["start"],pp["end"]),(gg["start"],gg["end"]))>=iou_th)
                if ok:
                    best_i=i; best=1; break
            if best_i>=0:
                matched[best_i]=True; used[j]=True
                TP[pp["label"]]+=1
            else:
                FP[pp["label"]]+=1
        for i,gg in enumerate(g):
            labels.add(gg["label"])
            if not matched[i]:
                FN[gg["label"]]+=1
        for j,pp in enumerate(p):
            labels.add(pp["label"])
    # 指標
    def prf(lab):
        tp,fp,fn=TP[lab],FP[lab],FN[lab]
        P = tp/(tp+fp) if (tp+fp)>0 else 0.0
        R = tp/(tp+fn) if (tp+fn)>0 else 0.0
        F1 = (2*P*R/(P+R)) if (P+R)>0 else 0.0
        return P,R,F1,tp,fp,fn
    macro = sum(prf(l)[2] for l in labels)/len(labels) if labels else 0.0
    mic_tp=sum(TP.values()); mic_fp=sum(FP.values()); mic_fn=sum(FN.values())
    micP = mic_tp/(mic_tp+mic_fp) if (mic_tp+mic_fp)>0 else 0.0
    micR = mic_tp/(mic_tp+mic_fn) if (mic_tp+mic_fn)>0 else 0.0
    micF = (2*micP*micR/(micP+micR)) if (micP+micR)>0 else 0.0
    rows=[(l,)+prf(l) for l in sorted(labels)]
    return {"macro":macro, "micro":(micP,micR,micF), "rows":rows}

strict = eval_mode("strict")
lenient = eval_mode("lenient")

ts=os.popen("date +%Y%m%dT%H%M%S").read().strip()
out_dir = Path(f"reports_auto/kie_eval/{ts}")
out_dir.mkdir(parents=True, exist_ok=True)
md = []
md.append("# KIE span metrics (model preds)")
md.append(f"- gold_file: {gold_merged}")
md.append(f"- pred_files: {len(pred_files)} (kept spans >= {min_conf}) total_kept_spans={pred_count}")
md.append(f"- micro P/R/F1 (strict): {strict['micro'][0]:.3f}/{strict['micro'][1]:.3f}/{strict['micro'][2]:.3f}")
md.append(f"- macro F1 (strict): {strict['macro']:.3f}")
md.append("")
md.append("|label|P|R|F1|TP|FP|FN|")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for (lab,P,R,F1,tp,fp,fn) in strict["rows"]:
    md.append(f"|{lab}|{P:.3f}|{R:.3f}|{F1:.3f}|{tp}|{fp}|{fn}|")
md.append("")
md.append("## lenient (IoU≥{:.2f})".format(iou_th))
md.append(f"- micro P/R/F1 (lenient): {lenient['micro'][0]:.3f}/{lenient['micro'][1]:.3f}/{lenient['micro'][2]:.3f}")
md.append(f"- macro F1 (lenient): {lenient['macro']:.3f}")
md.append("|label|P|R|F1|TP|FP|FN|")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for (lab,P,R,F1,tp,fp,fn) in lenient["rows"]:
    md.append(f"|{lab}|{P:.3f}|{R:.3f}|{F1:.3f}|{tp}|{fp}|{fn}|")

(Path(out_dir)/"metrics_kie_spans.md").write_text("\n".join(md), "utf-8")

# 也附加到最新 ONECLICK 摘要
try:
    import subprocess, glob as g
    latest = sorted(g.glob("reports_auto/status/ONECLICK_*.md"), key=os.path.getmtime)[-1]
    with open(latest,"a",encoding="utf-8") as f:
        f.write("\n\n## KIE span metrics (hotfix v2)\n")
        f.write("\n".join(md))
    print(f"[OK] appended metrics to {latest}")
except Exception as e:
    print("[WARN] append ONECLICK failed:", e)

print(f"[OK] wrote {out_dir}/metrics_kie_spans.md")
PY
