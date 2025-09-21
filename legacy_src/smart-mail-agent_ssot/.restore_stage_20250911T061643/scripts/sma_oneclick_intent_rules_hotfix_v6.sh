#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "data/intent_eval"

python - <<'PY'
# -*- coding: utf-8 -*-
import json, re, time
from pathlib import Path
from collections import Counter

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)

ds_p = ROOT/"data/intent_eval/dataset.jsonl"
if not ds_p.exists() or ds_p.stat().st_size==0:
    print("[FATAL] intent_eval/dataset.jsonl 不存在或為空"); raise SystemExit(2)

def read_jsonl(p):
    out=[]; 
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

ds = read_jsonl(ds_p)
texts=[(r.get("text") or r.get("body") or r.get("subject") or "") for r in ds]
gold =[r.get("intent") or r.get("label") or "其他" for r in ds]

# ---- 規則（精簡可維護版）----
# 以「先命中先停、再依優先級」策略：投訴 > 技術支援 > 資料異動 > 規則詢問 > 報價 > 其他
rules = [
    ("投訴", re.compile(r"(投訴|抱怨|不滿|申訴|退費|客訴)", re.I)),
    ("技術支援", re.compile(r"(無法|錯誤|error|failed|failure|當機|故障|bug|401|403|500|timeout|登入|staging|prod|環境|崩潰)", re.I)),
    ("資料異動", re.compile(r"(更新|更改|修改|變更).*(資料|資訊|公司|發票|抬頭|地址|電話)", re.I)),
    ("規則詢問", re.compile(r"(政策|規範|SLA|合約|條款|授權|license|隱私|資安|文件|manual|說明)", re.I)),
    ("報價", re.compile(r"(報價|費用|價格|估價|報.*?價|報價單)", re.I)),
]
ALLOW = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]

pred=[]
for t in texts:
    lab="其他"
    for name,rx in rules:
        if rx.search(t or ""):
            lab=name; break
    pred.append(lab)

# ---- 指標 ----
L2I={k:i for i,k in enumerate(ALLOW)}
import numpy as np
y_true=np.array([L2I.get(x, L2I["其他"]) for x in gold])
y_pred=np.array([L2I.get(x, L2I["其他"]) for x in pred])

def prf_conf(y_true,y_pred,labels):
    from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
    P,R,F1,Support = precision_recall_fscore_support(y_true,y_pred,labels=list(range(len(labels))),zero_division=0)
    macro_f1=float(np.mean(F1))
    micro_p,micro_r,micro_f1,_ = precision_recall_fscore_support(y_true,y_pred,average="micro",zero_division=0)
    cm = confusion_matrix(y_true,y_pred,labels=list(range(len(labels))))
    # 表格
    rows=["|label|P|R|F1|TP|FP|FN|","|---|---:|---:|---:|---:|---:|---:|"]
    for i,lab in enumerate(labels):
        tp=int(cm[i,i])
        fp=int(cm[:,i].sum()-tp)
        fn=int(cm[i,:].sum()-tp)
        rows.append(f"|{lab}|{P[i]:.3f}|{R[i]:.3f}|{F1[i]:.3f}|{tp}|{fp}|{fn}|")
    # 混淆
    cm_rows=["|gold\\pred|"+"|".join(labels)+"|","|---|"+"|".join(["---"]*len(labels))+"|"]
    for i,lab in enumerate(labels):
        cm_rows.append("|"+lab+"|"+"|".join(str(int(x)) for x in cm[i])+"|")
    return micro_p,micro_r,micro_f1,macro_f1,"\n".join(rows),"\n".join(cm_rows)

mi_p,mi_r,mi_f1,ma_f1,tab,cm_tab = prf_conf(y_true,y_pred,ALLOW)

md=[]
md.append("# Intent metrics (rules hotfix v6)")
md.append(f"- dataset: {ds_p.as_posix()}  size={len(ds)}")
md.append(f"- micro P/R/F1: {mi_p:.3f}/{mi_r:.3f}/{mi_f1:.3f}")
md.append(f"- macro F1: {ma_f1:.3f}\n")
md.append(tab+"\n")
md.append("## Confusion Matrix\n"+cm_tab+"\n")

# 輸出
out = EVADIR/"metrics_intent_rules_hotfix_v6.md"
out.write_text("\n".join(md), encoding="utf-8")
print(f"[OK] wrote {out.as_posix()}")

# 附掛 ONECLICK（若存在）
status = sorted((ROOT/"reports_auto/status").glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if status:
    st = status[0]
    with st.open("a+", encoding="utf-8") as f:
        f.write("\n## Intent metrics (rules hotfix v6)\n")
        f.write(out.read_text("utf-8"))
    print(f"[OK] appended metrics to {st.as_posix()}")

print(f">>> Result => {out.as_posix()}")
PY
