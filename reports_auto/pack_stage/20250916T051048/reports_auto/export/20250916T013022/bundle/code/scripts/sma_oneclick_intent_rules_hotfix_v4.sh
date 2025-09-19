#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "data/intent_eval"

python - <<'PY'
# -*- coding: utf-8 -*-
import json, re, time, pickle, os, math
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(".")
NOW  = time.strftime("%Y%m%dT%H%M%S")
EVADIR = ROOT/f"reports_auto/eval/{NOW}"
EVADIR.mkdir(parents=True, exist_ok=True)

ALLOW = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]
PRI = {k:i for i,k in enumerate(ALLOW)}  # 排序穩定

def read_jsonl(p):
    out=[]
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

# 1) 載資料（金標）
ds_p = ROOT/"data/intent_eval/dataset.jsonl"
if not ds_p.exists() or ds_p.stat().st_size==0:
    print("[SKIP] data/intent_eval/dataset.jsonl 不存在或為空，略過 Intent 評測")
    raise SystemExit(0)
raw = read_jsonl(ds_p)
X = [r.get("text") or r.get("body") or r.get("subject") or "" for r in raw]
y = [r.get("intent") or r.get("label") or "其他" for r in raw]
y = [lb if lb in ALLOW else "其他" for lb in y]

# 2) 門檻
th_p = ROOT/"reports_auto/intent_thresholds.json"
th = {"報價":0.30,"技術支援":0.30,"投訴":0.30,"規則詢問":0.30,"資料異動":0.30,"其他":0.40}
if th_p.exists():
    try: th.update(json.loads(th_p.read_text("utf-8")))
    except: pass

# 3) 規則（簡明且可調）
RX = {
  "報價": re.compile(r"報價|報個價|報價單|估價|報價表|NT\$|TWD|新台幣|台幣|\$\d", re.I),
  "技術支援": re.compile(r"無法|錯誤|失敗|exception|crash|timeout|逾時|401|403|404|500|登入|連不上|壞掉|卡住", re.I),
  "投訴": re.compile(r"不滿|抱怨|客訴|投訴|申訴|退費|賠償|抗議", re.I),
  "規則詢問": re.compile(r"SLA|SLO|SLI|資安|政策|規範|文件|授權|license|條款|隱私|合約|SOP", re.I),
  "資料異動": re.compile(r"(更新|變更|修改|更正).*(資料|聯絡|抬頭|發票|地址|電話|公司)", re.I),
}

RULE_SCORE = 0.98

# 4) 取模型（可選）
proba = []
model_p = ROOT/"artifacts/intent_pro_cal.pkl"
model = None
if model_p.exists() and model_p.stat().st_size>0:
    try:
        model = pickle.loads(model_p.read_bytes())
    except Exception as e:
        print("[WARN] intent_pro_cal.pkl 載入失敗，僅用規則+門檻：", e)

if model is not None:
    try:
        P = model.predict_proba(X)  # 假設順序與 classes_ 對齊
        classes = list(getattr(model,"classes_",[])) or list(getattr(model,"named_steps",{}).get("clf",None).classes_)
        cidx = {c:i for i,c in enumerate(classes)}
        for i,txt in enumerate(X):
            score = {lb: float(P[i][cidx[lb]]) if lb in cidx else 0.0 for lb in ALLOW}
            # 規則疊加
            for lb,rgx in RX.items():
                if rgx.search(txt): score[lb] = max(score[lb], RULE_SCORE)
            proba.append(score)
    except Exception as e:
        print("[WARN] predict_proba 失敗，用規則 default：", e)

# 沒有模型 => 純規則
if not proba:
    for txt in X:
        s={lb:0.0 for lb in ALLOW}
        for lb,rgx in RX.items():
            if rgx.search(txt): s[lb]=RULE_SCORE
        proba.append(s)

# 5) 依門檻決策（未達門檻者 → 其他）
def decide(score:dict):
    # 取達門檻的最高；否則回「其他」
    best=("其他",-1.0)
    for lb in ALLOW:
        sc=score.get(lb,0.0)
        if sc>=th.get(lb,0.0) and sc>best[1]: best=(lb,sc)
    return best[0]

y_pred = [decide(s) for s in proba]

# 6) 指標
labs = ALLOW
cm = {a:{b:0 for b in labs} for a in labs}
for g,p in zip(y,y_pred): cm[g][p]+=1

def prf(lbl):
    TP=cm[lbl][lbl]
    FP=sum(cm[g][lbl] for g in labs if g!=lbl)
    FN=sum(cm[lbl][p] for p in labs if p!=lbl)
    P = TP/(TP+FP) if TP+FP>0 else 0.0
    R = TP/(TP+FN) if TP+FN>0 else 0.0
    F1= (2*P*R)/(P+R) if P+R>0 else 0.0
    return P,R,F1,TP,FP,FN

rows=[]
microTP=microFP=microFN=0
for lb in labs:
    P,R,F1,TP,FP,FN = prf(lb)
    rows.append((lb,P,R,F1,TP,FP,FN))
    microTP+=TP; microFP+=FP; microFN+=FN
macroF = sum(r[2] for r in rows)/len(rows)
microP = microTP/(microTP+microFP) if microTP+microFP>0 else 0.0
microR = microTP/(microTP+microFN) if microTP+microFN>0 else 0.0
microF = (2*microP*microR)/(microP+microR) if microP+microR>0 else 0.0

# 7) 難例（每類 <=30）
hard = defaultdict(list)
for txt,gt,sc,pd in zip(X,y,proba,y_pred):
    if gt!=pd and len(hard[gt])<30:
        hard[gt].append({"text":txt,"gold":gt,"pred":pd,"scores":sc})
hard_p = EVADIR/"intent_unmatched.jsonl"
with hard_p.open("w",encoding="utf-8") as f:
    for lb in labs:
        for it in hard[lb]:
            f.write(json.dumps(it,ensure_ascii=False)+"\n")

# 8) Output md
md=[]
md.append("# Intent metrics (rules + thresholds [+ model])")
md.append(f"- dataset: data/intent_eval/dataset.jsonl  size={len(X)}")
md.append(f"- thresholds: {json.dumps(th,ensure_ascii=False)}")
md.append(f"- micro P/R/F1: {microP:.3f}/{microR:.3f}/{microF:.3f}")
md.append(f"- macro F1: {macroF:.3f}\n")
md.append("|label|P|R|F1|TP|FP|FN|")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for lb,P,R,F1,TP,FP,FN in rows:
    md.append(f"|{lb}|{P:.3f}|{R:.3f}|{F1:.3f}|{TP}|{FP}|{FN}|")

md.append("\n## Confusion Matrix")
md.append("|gold\\pred|"+"|".join(labs)+"|")
md.append("|---|"+"|".join(["---"]*len(labs))+"|")
for g in labs:
    md.append("|"+g+"|"+"|".join(str(cm[g][p]) for p in labs)+"|")

md.append(f"\n- unmatched examples -> {hard_p.as_posix()}")

md_p = EVADIR/"metrics_intent_rules_hotfix.md"
(Path(md_p)).write_text("\n".join(md),encoding="utf-8")
print(f"[OK] wrote {md_p}")

# 9) 附到 ONECLICK 摘要
st_dir = ROOT/"reports_auto/status"
if st_dir.exists():
    latest = sorted(st_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
    if latest:
        with latest[0].open("a",encoding="utf-8") as f:
            f.write("\n## Intent metrics (rules hotfix v4)\n")
            f.write(Path(md_p).read_text("utf-8"))
        print(f"[OK] appended metrics to {latest[0].as_posix()}")
PY

LATEST="$(ls -td reports_auto/eval/* | head -n1)"
echo ">>> Result => $LATEST/metrics_intent_rules_hotfix.md"
sed -n '1,120p' "$LATEST/metrics_intent_rules_hotfix.md" || true
echo ">>> Unmatched => $LATEST/intent_unmatched.jsonl"
