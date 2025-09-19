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
import re, json, time
from pathlib import Path
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)
ds_p=ROOT/"data/intent_eval/dataset.jsonl"
assert ds_p.exists() and ds_p.stat().st_size>0, "intent_eval/dataset.jsonl 不存在或為空"

def read_jsonl(p):
    out=[]
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if ln:
            try: out.append(json.loads(ln))
            except: pass
    return out

ds=read_jsonl(ds_p)
txts=[(r.get("text") or r.get("body") or r.get("subject") or "") for r in ds]
gold=[r.get("intent") or r.get("label") or "其他" for r in ds]

ALLOW=["報價","技術支援","投訴","規則詢問","資料異動","其他"]
L2I={k:i for i,k in enumerate(ALLOW)}

# ===== 關鍵訊號 =====
RX_PRICE   = re.compile(r"(報\s*價|報價單|估\s*價|費用|價格|單價|總價|報個?價|pricing|quotation|quote|費率|報價表)", re.I)
RX_MONEY   = re.compile(r"(NT\$|新台幣|USD|US\$|\$|元|萬元|千元)", re.I)
RX_NUMBER  = re.compile(r"\d")
RX_PEOPLEQ = re.compile(r"(?:\d+\s*)(位|人|台|套|年|月|季|份|票|筆)", re.I)

RX_TECH    = re.compile(r"(無法|錯誤|錯碼|error|failed|failure|當機|故障|bug|崩潰|timeout|逾時|連線|登入|登出|密碼|授權失敗|401|403|404|500|502|503|504|staging|prod|production|sandbox|環境)", re.I)
RX_COMPLA  = re.compile(r"(投訴|抱怨|不滿|申訴|退費|客訴|黑名單)", re.I)
RX_UPDATE  = re.compile(r"(更新|更改|修改|變更).*(資料|資訊|公司|發票|抬頭|地址|電話|聯絡|統編|統一編號)", re.I)

RX_POLICY  = re.compile(r"(SLA|政策|規範|合約|條款|NDA|授權|license|隱私|資安|GDPR|ISO|SOC\s*2|滲透測試|稽核|合規|白皮書|compliance)", re.I)
RX_DOCS    = re.compile(r"(文件|手冊|manual|說明|API\s*文件|SDK\s*下載|產品簡介)", re.I)

def looks_like_pricing(text):
    return bool(RX_PRICE.search(text) or (RX_MONEY.search(text) and RX_NUMBER.search(text))) or bool(RX_PEOPLEQ.search(text))

def detect_intent(text):
    t = text or ""
    # 1) 投訴
    if RX_COMPLA.search(t): return "投訴"
    # 2) 技術支援
    if RX_TECH.search(t):  return "技術支援"
    # 3) 資料異動
    if RX_UPDATE.search(t): return "資料異動"
    # 4) 報價（提到價格/幣別/數字或明示報價）
    if looks_like_pricing(t): return "報價"
    # 5) 規則詢問（含 API/SDK 文件 & 政策資安），但若有強價格訊號則讓步給報價
    if RX_POLICY.search(t) or RX_DOCS.search(t):
        if not looks_like_pricing(t):
            return "規則詢問"
        # 有價格訊號則視為報價
        return "報價"
    # 6) 其他
    return "其他"

pred=[detect_intent(t) for t in txts]

y_true=np.array([L2I.get(x, L2I["其他"]) for x in gold])
y_pred=np.array([L2I.get(x, L2I["其他"]) for x in pred])

P,R,F1,Supp = precision_recall_fscore_support(y_true,y_pred,labels=list(range(len(ALLOW))),zero_division=0)
macro_f1=float(np.mean(F1))
mi_p,mi_r,mi_f1,_ = precision_recall_fscore_support(y_true,y_pred,average="micro",zero_division=0)
cm = confusion_matrix(y_true,y_pred,labels=list(range(len(ALLOW))))

# 報表
rows=["|label|P|R|F1|TP|FP|FN|","|---|---:|---:|---:|---:|---:|---:|"]
for i,lab in enumerate(ALLOW):
    tp=int(cm[i,i]); fp=int(cm[:,i].sum()-tp); fn=int(cm[i,:].sum()-tp)
    rows.append(f"|{lab}|{P[i]:.3f}|{R[i]:.3f}|{F1[i]:.3f}|{tp}|{fp}|{fn}|")

cm_rows=["|gold\\pred|"+"|".join(ALLOW)+"|","|---|"+"|".join(["---"]*len(ALLOW))+"|"]
for i,lab in enumerate(ALLOW):
    cm_rows.append("|"+lab+"|"+"|".join(str(int(x)) for x in cm[i])+"|")

md=[]
md.append("# Intent metrics (rules hotfix v7)")
md.append(f"- dataset: {ds_p.as_posix()}  size={len(ds)}")
md.append(f"- micro P/R/F1: {mi_p:.3f}/{mi_r:.3f}/{mi_f1:.3f}")
md.append(f"- macro F1: {macro_f1:.3f}\n")
md.append("\n".join(rows)+"\n")
md.append("## Confusion Matrix\n"+ "\n".join(cm_rows) + "\n")

out_md = EVADIR/"metrics_intent_rules_hotfix_v7.md"
out_md.write_text("\n".join(md), encoding="utf-8")
print(f"[OK] wrote {out_md.as_posix()}")

# 錯分樣本導出（每類最多 80 筆）
bad = []
for i,(t,g,p) in enumerate(zip(txts,gold,pred)):
    if g!=p:
        bad.append({"idx":i,"gold":g,"pred":p,"text":t})
bad_p = EVADIR/"intent_miscls_v7.jsonl"
with bad_p.open("w", encoding="utf-8") as f:
    for r in bad[:2000]:
        f.write(json.dumps(r, ensure_ascii=False)+"\n")
print(f"[OK] dumped misclassifications -> {bad_p.as_posix()} (count={len(bad)})")

# 附掛 ONECLICK
status = sorted((ROOT/"reports_auto/status").glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if status:
    st = status[0]
    with st.open("a+", encoding="utf-8") as f:
        f.write("\n## Intent metrics (rules hotfix v7)\n")
        f.write(out_md.read_text("utf-8"))
    print(f"[OK] appended metrics to {st.as_posix()}")

print(f">>> Result => {out_md.as_posix()}")
PY
