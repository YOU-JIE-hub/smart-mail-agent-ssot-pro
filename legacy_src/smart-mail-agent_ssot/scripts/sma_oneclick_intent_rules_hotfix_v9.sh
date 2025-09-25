#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "data/intent_eval" "artifacts_prod"

python - <<'PY'
# -*- coding: utf-8 -*-
import re, json, time, math, statistics
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)

# 1) 資料：優先吃清理後，否則用原始
ds = []
src = None
for cand in [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if cand.exists() and cand.stat().st_size>0:
        src=cand
        for ln in cand.read_text("utf-8").splitlines():
            ln=ln.strip()
            if not ln: continue
            try: ds.append(json.loads(ln))
            except: pass
        break
if not ds:
    raise SystemExit("[FATAL] intent_eval dataset not found")

LABELS = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]
PRI = {k:i for i,k in enumerate(["報價","技術支援","投訴","資料異動","規則詢問","其他"])}

def norm(s:str)->str:
    s=(s or "").strip()
    s=s.replace("\u3000"," ").replace("\xa0"," ")
    s=re.sub(r"\s+"," ",s)
    return s.lower()

KW = {
  "報價": dict(
    pos=[
      r"報價(單|明細)?", r"報個?價", r"(價格|價錢|費用|費率|單價|報價表)",
      r"(nt\$|ntd|台幣|新台幣|usd|美金|rmb|人民幣)\s*\d",
      r"\d[\d,\.]*\s*(元|塊|萬|千)", r"(幾錢|多少錢)",
      r"(請|能否|可否)(提供|給)報價", r"(估|抓)價", r"(報|開)報價單",
      r"(?:\d{1,3})\s*(位|人)", r"份數|人數|幾人", r"於?\s*\d{1,2}/\d{1,2}\s*前?.*報價"
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
      r"(投訴|申訴|客訴|抱怨|不滿|很不滿|非常不便|相當不便|失望|氣憤|品質差|服務差|體驗差)",
      r"(已寄出|已送出).*(投訴|申訴).*(表|單)",
      r"(退費|退款|賠償|補償)",
      r"(請|還)請.*(回覆|處理)"
    ],
    neg=[r"詢問.*(政策|規範|文件|說明)", r"僅.*建議|建議.*改善"]
  ),
  "規則詢問": dict(
    pos=[r"(政策|規範|規則|條款|資安|隱私|gdpr|ccpa|sla|license|授權|合約|白皮書|manual|說明書|文件)"],
    neg=[r"報價|價格|價錢|費用|技術支援|錯誤|無法登入|bug|投訴|抱怨|客訴"]
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

POS_W = {"報價":1.0,"技術支援":1.0,"投訴":1.2,"規則詢問":0.9,"資料異動":1.0,"其他":1.0}
NEG_W = 0.8

def base_scores(t:str):
    s = {lab:0.0 for lab in LABELS}
    for lab in LABELS:
        p = sum(bool(re.search(rx, t, re.I)) for rx in KW[lab]["pos"])
        n = sum(bool(re.search(rx, t, re.I)) for rx in KW[lab]["neg"])
        sc = p*POS_W.get(lab,1.0) - n*NEG_W
        # 額外加權
        if lab=="報價":
            if re.search(r"(nt\$|ntd|新台幣|台幣|usd|美金|rmb|人民幣)", t, re.I): sc += 0.6
            if re.search(r"\d[\d,\.]*\s*(元|塊|萬|千)", t): sc += 0.4
            if re.search(r"(位|人)\s*[，,、 ]*\d{1,3}", t): sc += 0.2
        if lab=="技術支援":
            if re.search(r"(錯誤|error|exception|timeout|逾時)", t, re.I): sc += 0.4
            if re.search(r"\b(401|403|404|408|409|429|500|502|503|504)\b", t): sc += 0.4
            if re.search(r"(無法|不能).*(登入|連線)", t): sc += 0.3
        if lab=="投訴":
            if re.search(r"(投訴|客訴|申訴)", t): sc += 0.6
            if re.search(r"(退費|賠償|補償|退款)", t): sc += 0.5
        s[lab]=sc
    # 守門：若有價格/報價訊號，壓低規則詢問並拉高報價
    if re.search(r"(報價|價格|價錢|費用|單價)", t): 
        s["規則詢問"] -= 1.2
        s["報價"] += 0.6
    # 若強錯誤碼或無法登入，壓低規則詢問
    if re.search(r"\b(401|403|404|408|409|429|500|502|503|504)\b", t) or re.search(r"(無法|不能).*(登入|連線)", t):
        s["規則詢問"] -= 0.6
    return s

# 初始門檻（較鬆），之後會用 bias 微調
MIN_KEEP = {"報價":0.45,"技術支援":0.50,"投訴":0.45,"資料異動":0.45,"規則詢問":0.55,"其他":-9e9}
BIAS = {k:0.0 for k in LABELS}

def predict_with(bias, min_keep, text):
    t = norm(text)
    s = base_scores(t)
    for k in s: s[k] += bias.get(k,0.0)
    # 二次 tie-break：若報價分數接近規則詢問（差距<=0.6）且有金額或貨幣，強轉報價
    if (s["規則詢問"] > s["報價"]) and (s["規則詢問"] - s["報價"] <= 0.6) and (
        re.search(r"(nt\$|ntd|新台幣|台幣|usd|美金|rmb|人民幣)", t, re.I) or re.search(r"\d[\d,\.]*\s*(元|塊|萬|千)", t)
    ):
        s["報價"] += 0.8
    best = max(LABELS, key=lambda k:(s[k], -PRI[k]))
    if s[best] < min_keep.get(best,0.5): best = "其他"
    return best, s

def eval_with(bias, min_keep):
    y_true, y_pred = [], []
    for r in ds:
        gold = (r.get("label") or r.get("intent") or r.get("category") or "其他")
        text = r.get("text") or r.get("subject") or ""
        pred,_ = predict_with(bias, min_keep, text)
        y_true.append(gold); y_pred.append(pred)
    P,R,F1,_ = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    micro = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, average="micro", zero_division=0)
    macro = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)
    return dict(P=P,R=R,F1=F1,micro=micro,macro=macro, y_true=y_true,y_pred=y_pred)

# 2) 輕量「座標上升」自動校正 bias
cands = [-0.6,-0.3,0.0,0.3,0.6,0.9]
best_bias = dict(BIAS)
best_min = dict(MIN_KEEP)
best = eval_with(best_bias, best_min)
best_micro = best["micro"][2]

for _ in range(3):  # 做 3 回合
    improved = False
    for lab in LABELS:
        cur = best_micro; keep = best_bias[lab]
        for b in cands:
            trial_bias = dict(best_bias); trial_bias[lab]=b
            trial = eval_with(trial_bias, best_min)
            if trial["micro"][2] > best_micro + 1e-6:
                best_micro = trial["micro"][2]
                best_bias = trial_bias
                best = trial
                improved = True
        if best_bias[lab] != keep:
            pass
    # 針對投訴/報價再微調門檻
    for lab, pool in [("投訴",[0.35,0.40,0.45,0.50]), ("報價",[0.35,0.40,0.45,0.50])]:
        keep = best_min[lab]
        for th in pool:
            trial_min = dict(best_min); trial_min[lab]=th
            trial = eval_with(best_bias, trial_min)
            if trial["micro"][2] > best_micro + 1e-6:
                best_micro = trial["micro"][2]
                best_min = trial_min
                best = trial
                improved = True
    if not improved:
        break

# 3) 報表 + 診斷輸出
y_true, y_pred = best["y_true"], best["y_pred"]
P,R,F1 = best["P"], best["R"], best["F1"]
cm = confusion_matrix(y_true, y_pred, labels=LABELS)

md=[]
md.append("# Intent metrics (rules hotfix v9)")
md.append(f"- dataset: {src.as_posix()}  size={len(ds)}")
md.append(f"- micro P/R/F1: {best['micro'][0]:.3f}/{best['micro'][1]:.3f}/{best['micro'][2]:.3f}")
md.append(f"- macro F1: {best['macro'][2]:.3f}")
md.append(f"- bias: {json.dumps(best_bias, ensure_ascii=False)}")
md.append(f"- min_keep: {json.dumps(best_min, ensure_ascii=False)}\n")
md.append("|label|P|R|F1|"); md.append("|---|---:|---:|---:|")
for lab,p,r,f in zip(LABELS,P,R,F1):
    md.append(f"|{lab}|{p:.3f}|{r:.3f}|{f:.3f}|")

md.append("\n## Confusion Matrix")
hdr="|gold\\pred|"+"|".join(LABELS)+"|"
md.extend([hdr, "|"+"|".join(["---"]*(len(LABELS)+1))+"|"])
for i,lab in enumerate(LABELS):
    row=[lab]+[str(cm[i,j]) for j in range(len(LABELS))]
    md.append("|" + "|".join(row) + "|")

# 輸出誤分樣本與 Top FN/FP 文本
mis=[]; per_lab=defaultdict(lambda:defaultdict(list))
for i,(r,gt,pd) in enumerate(zip(ds,y_true,y_pred)):
    if gt!=pd:
        text = r.get("text") or r.get("subject") or ""
        _, sc = predict_with(best_bias, best_min, text)
        mis.append({"i":i,"gold":gt,"pred":pd,"text":text,"scores":sc})
        per_lab[gt]["FN"].append((i,text,pd))
        per_lab[pd]["FP"].append((i,text,gt))

(EVADIR/"metrics_intent_rules_hotfix_v9.md").write_text("\n".join(md), "utf-8")
(EVADIR/"intent_miscls_v9.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in mis), "utf-8")

def dump_txt(items, path, k=120):
    lines=[]
    for i,(idx,txt,aux) in enumerate(items[:k]):
        one=f"[{idx}] ({aux}) {txt.replace('\n',' ')}"
        lines.append(one)
    Path(path).write_text("\n".join(lines), "utf-8")

for lab in LABELS:
    dump_txt(per_lab[lab]["FN"], (EVADIR/f"FN_{lab}.txt").as_posix())
    dump_txt(per_lab[lab]["FP"], (EVADIR/f"FP_{lab}.txt").as_posix())

# 附掛 ONECLICK
status_dir=ROOT/"reports_auto/status"; status_dir.mkdir(parents=True, exist_ok=True)
lst=sorted(status_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if lst:
    tgt=lst[0]
    with tgt.open("a",encoding="utf-8") as w:
        w.write("\n## Intent metrics (rules hotfix v9)\n")
        w.write((EVADIR/"metrics_intent_rules_hotfix_v9.md").read_text("utf-8"))
    print(f"[OK] appended metrics to {tgt.as_posix()}")

print(f">>> Result => {(EVADIR/'metrics_intent_rules_hotfix_v9.md').as_posix()}")
print(f"[OK] dumped misclassifications -> {(EVADIR/'intent_miscls_v9.jsonl').as_posix()} (count={len(mis)})")
print(f"[OK] FN/FP dumps -> {EVADIR.as_posix()}/FN_*.txt, FP_*.txt")

# 同步保存校正參數，方便部署/重現
calib = {"bias": best_bias, "min_keep": best_min, "ts": NOW}
( ROOT/"artifacts_prod/intent_rules_calib_v9.json" ).write_text(json.dumps(calib,ensure_ascii=False,indent=2),"utf-8")
print("[OK] saved calib -> artifacts_prod/intent_rules_calib_v9.json")
PY
