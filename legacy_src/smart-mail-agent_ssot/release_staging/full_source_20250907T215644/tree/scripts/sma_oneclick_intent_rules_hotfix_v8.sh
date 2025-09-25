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
import re, json, time, math
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)

# 1) 載資料（優先用清洗後）
ds = []
for cand in [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if cand.exists() and cand.stat().st_size>0:
        for ln in cand.read_text("utf-8").splitlines():
            if not ln.strip(): continue
            ds.append(json.loads(ln))
        src = cand
        break
else:
    raise SystemExit("[FATAL] 找不到 intent 資料集")

ALLOW = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]
PRI = {k:i for i,k in enumerate(["報價","技術支援","投訴","資料異動","規則詢問","其他"])}  # 優先序

def norm(s:str)->str:
    s = s.strip()
    s = s.replace("\u3000"," ").replace("\xa0"," ")
    s = re.sub(r"\s+", " ", s)
    s = s.lower()
    return s

# 2) 規則庫（可持續擴充）
KW = {
  "報價": dict(
    pos=[
      r"報價(單|明細)?", r"報個?價", r"(價格|價錢|費用|費率|單價|報酬|報價表)",
      r"(nt\$|ntd|台幣|新台幣|usd|美金|rmb|人民幣)\s*\d",
      r"\d[\d,\.]*\s*(元|塊|萬|千)", r"(幾錢|多少錢)",
      r"(請|能否|可否)(提供|給)報價", r"(估|抓)價", r"(報|開)報價單"
    ],
    neg=[r"政策|規範|條款|sla|文件|說明書|license|授權|合約"]
  ),
  "技術支援": dict(
    pos=[
      r"(無法|不能|沒辦法).*(登入|連線|上傳|下載|開啟|執行)",
      r"(錯誤|error|failed|exception|bug|crash|當機)",
      r"\b(401|403|404|408|409|429|500|502|503|504)\b",
      r"(staging|prod(uction)?|測試|正式|沙盒|sandbox)",
      r"(憑證|token|oauth|api key|rate limit|逾時|timeout)"
    ],
    neg=[r"報價|價格|費用|投訴|抱怨|客訴"]
  ),
  "投訴": dict(
    pos=[
      r"(投訴|申訴|客訴|抱怨|抱歉.*造成.*不便|相當不便|非常不便|不滿|很不滿|失望|氣憤|品質差|服務差|體驗差)",
      r"(已寄出|已送出).*(投訴|申訴).*(表|單)",
      r"(請|還)請.*(回覆|處理)", r"(退費|退款|賠償|補償)"
    ],
    neg=[r"詢問.*(政策|規範|文件|說明)", r"僅.*建議|建議.*改善"]
  ),
  "規則詢問": dict(
    pos=[r"(政策|規範|規則|條款|政策文件|資安|隱私|gdpr|ccpa|sla|license|授權|合約|白皮書|manual|說明書|文件)"],
    neg=[r"報價|價格|費用|技術支援|錯誤|無法登入|bug|投訴|抱怨|客訴"]
  ),
  "資料異動": dict(
    pos=[
      r"(更新|變更|修改|更正|請.*修正).*(資料|資訊|聯絡|地址|電話|email|e-mail|發票|抬頭|統編|invoice)",
      r"(新增|刪除).*(聯絡(人)?|白名單|whitelist|黑名單|blacklist)"
    ],
    neg=[r"報價|價格|費用|錯誤|bug"]
  ),
  "其他": dict(pos=[], neg=[])
}

def score_label(txt:str, lab:str)->float:
    p = sum(bool(re.search(rx, txt, re.I)) for rx in KW[lab]["pos"])
    n = sum(bool(re.search(rx, txt, re.I)) for rx in KW[lab]["neg"])
    sc = p*1.0 - n*0.8
    # 額外加權
    if lab=="報價":
        if re.search(r"(nt\$|ntd|新台幣|台幣|usd|美金|rmb|人民幣)", txt, re.I): sc += 0.5
        if re.search(r"\d[\d,\.]*\s*(元|塊|萬|千)", txt): sc += 0.3
        if re.search(r"(位|人)\s*[，,、 ]*\d{1,3}", txt): sc += 0.2
    if lab=="技術支援":
        if re.search(r"(錯誤|error|exception|timeout|逾時)", txt, re.I): sc += 0.4
        if re.search(r"\b(401|403|404|408|409|429|500|502|503|504)\b", txt): sc += 0.3
        if re.search(r"(無法|不能).*(登入|連線)", txt): sc += 0.3
    if lab=="投訴":
        if re.search(r"(投訴|客訴|申訴)", txt): sc += 0.5
        if re.search(r"(退費|賠償|補償)", txt): sc += 0.4
    return sc

MIN_KEEP = {
  "報價": 0.6, "技術支援": 0.6, "投訴": 0.6, "資料異動": 0.6, "規則詢問": 0.6, "其他": -999
}

def predict_one(text:str):
    t = norm(text)
    scores = {lab: score_label(t, lab) for lab in ALLOW}
    # 規則詢問守門：若價錢/報價強匹配，直接壓低規則詢問
    if re.search(r"(報價|價格|價錢|費用)", t): scores["規則詢問"] -= 0.8
    # 取最高分，若分數都低於門檻則落到其他
    best = max(scores, key=lambda k:(scores[k], -PRI[k]))
    if scores[best] < MIN_KEEP.get(best, 0.6): best = "其他"
    return best, scores

y_true, y_pred = [], []
mis = []
for i, r in enumerate(ds):
    txt = r.get("text") or r.get("subject") or ""
    gold = r.get("label") or r.get("intent") or r.get("category") or "其他"
    pred, sc = predict_one(txt)
    y_true.append(gold); y_pred.append(pred)
    if pred != gold:
        mis.append({"i": i, "gold": gold, "pred": pred, "text": txt, "scores": sc})

labels = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]
P,R,F1,_ = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
micro = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="micro", zero_division=0)
macro = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="macro", zero_division=0)

cm = confusion_matrix(y_true, y_pred, labels=labels)

md = []
md.append("# Intent metrics (rules hotfix v8)")
md.append(f"- dataset: {src.as_posix()}  size={len(ds)}")
md.append(f"- micro P/R/F1: {micro[0]:.3f}/{micro[1]:.3f}/{micro[2]:.3f}")
md.append(f"- macro F1: {macro[2]:.3f}\n")
md.append("|label|P|R|F1|")
md.append("|---|---:|---:|---:|")
for lab,p,r,f in zip(labels,P,R,F1):
    md.append(f"|{lab}|{p:.3f}|{r:.3f}|{f:.3f}|")
md.append("\n## Confusion Matrix")
hdr = "|gold\\pred|"+"|".join(labels)+"|"
md.extend([hdr, "|"+"---|"*len(labels)+"---|"])
for i,lab in enumerate(labels):
    row = [lab]+[str(cm[i,j]) for j in range(len(labels))]
    md.append("|" + "|".join(row) + "|")

(EVADIR/"metrics_intent_rules_hotfix_v8.md").write_text("\n".join(md), "utf-8")
(EVADIR/"intent_miscls_v8.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in mis), "utf-8")

# 附掛到 ONECLICK 摘要
oneclick = ROOT/"reports_auto/status"
oneclick.mkdir(parents=True, exist_ok=True)
lst = sorted(oneclick.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if lst:
    tgt = lst[0]
    with tgt.open("a", encoding="utf-8") as w:
        w.write("\n## Intent metrics (rules hotfix v8)\n")
        w.write((EVADIR/"metrics_intent_rules_hotfix_v8.md").read_text("utf-8"))
    print(f"[OK] appended metrics to {tgt.as_posix()}")

print(f">>> Result => {(EVADIR/'metrics_intent_rules_hotfix_v8.md').as_posix()}")
print(f"[OK] dumped misclassifications -> {(EVADIR/'intent_miscls_v8.jsonl').as_posix()} (count={len(mis)})")
PY
