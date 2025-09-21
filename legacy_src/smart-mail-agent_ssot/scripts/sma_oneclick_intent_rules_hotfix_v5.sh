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
import json,re,time,os
from pathlib import Path
from collections import defaultdict

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)

ALLOW=["報價","技術支援","投訴","規則詢問","資料異動","其他"]

def read_jsonl(p):
    out=[]; 
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

ds_p=ROOT/"data/intent_eval/dataset.jsonl"
if not ds_p.exists() or ds_p.stat().st_size==0:
    print("[SKIP] data/intent_eval/dataset.jsonl 不存在或為空"); raise SystemExit(0)

raw=read_jsonl(ds_p)
X=[r.get("text") or r.get("body") or r.get("subject") or "" for r in raw]
y=[r.get("intent") or r.get("label") or "其他" for r in raw]
y=[lb if lb in ALLOW else "其他" for lb in y]

# ---- v5 規則：更嚴謹的“規則詢問” & 擴增“資料異動／技術支援／投訴／報價”
num_cur = r'(?:NT\$|TWD|新台幣|台幣|[\\$＄])\\s*\\d+[\\d,\\.]*'
rx = {
  "報價": [
    r"報價|報個價|報價單|估價|單價|報價表|費用|價格|多少錢|價錢|報.*價",
    rf"{num_cur}"
  ],
  "技術支援": [
    r"無法|失敗|錯誤|exception|crash|timeout|逾時|連不上|卡住|壞掉|當掉|重試|重設|憑證|驗證",
    r"\b401\b|\b403\b|\b404\b|\b500\b",
    r"登入|登錄|login|sign[- ]?in",
    r"\b(staging|prod|production|測試機|預備機)\b"
  ],
  "投訴": [
    r"不滿|抱怨|客訴|投訴|申訴|退費|賠償|抗議|差評|失望|很糟|很爛|服務太差|投訴表"
  ],
  "資料異動": [
    r"(更新|變更|修改|更正).*(資料|資訊|聯絡|抬頭|發票|統編|統一編號|地址|電話|公司|戶名|抬頭)",
    r"(請.*更新|請.*修改).*(資訊|資料|抬頭|發票|公司)"
  ],
  # 規則詢問：須含「主題關鍵詞」+（文件/下載/說明/政策等）才算，避免把一般“文件”都收進來
  "規則詢問": [
    r"(API|SDK|SLA|SLO|SLI|資安|安全|隱私|GDPR|ISO|SOC ?2|授權|license|商用|合約|條款)",
    r"(文件|說明|規範|policy|白皮書|下載|連結|doc|manual|指南)"
  ],
}

compiled = {k:[re.compile(pat, re.I) for pat in pats] for k,pats in rx.items()}

def score_text(txt:str):
    # 規則分數：命中條件數量越多，分數越高；“規則詢問”需雙條件成立
    s={k:0.0 for k in ALLOW}
    # 報價：有錢字＋“報價”詞加分
    if any(r.search(txt) for r in compiled["報價"]):
        hits=sum(1 for r in compiled["報價"] if r.search(txt)); s["報價"]=0.90+0.03*min(hits,3)
    # 技術支援：越多錯誤線索越高
    if any(r.search(txt) for r in compiled["技術支援"]):
        hits=sum(1 for r in compiled["技術支援"] if r.search(txt)); s["技術支援"]=0.86+0.03*min(hits,4)
    # 投訴
    if any(r.search(txt) for r in compiled["投訴"]):
        hits=sum(1 for r in compiled["投訴"] if r.search(txt)); s["投訴"]=0.90+0.02*min(hits,3)
    # 資料異動
    if any(r.search(txt) for r in compiled["資料異動"]):
        hits=sum(1 for r in compiled["資料異動"] if r.search(txt)); s["資料異動"]=0.88+0.03*min(hits,3)
    # 規則詢問：必須同時命中兩組（主題 + 輔助詞）
    rq = compiled["規則詢問"]
    if (rq[0].search(txt) and rq[1].search(txt)):
        s["規則詢問"]=0.88
        # 如果包含「API/SDK + 下載/文件」再多給一點
        if re.search(r"(API|SDK)", txt, re.I) and re.search(r"(下載|連結|文件|doc|guide|manual|說明)", txt, re.I):
            s["規則詢問"]=0.92
    # 其他：只有完全沒打中任何類才選“其他”
    if max(s.values())==0.0:
        s["其他"]=0.60
    return s

# 門檻
th={"報價":0.30,"技術支援":0.30,"投訴":0.30,"規則詢問":0.35,"資料異動":0.30,"其他":0.40}
th_p=ROOT/"reports_auto/intent_thresholds.json"
if th_p.exists():
    try:
        tmp=json.loads(th_p.read_text("utf-8"))
        th.update({k:float(v) for k,v in tmp.items() if k in th})
    except: pass

def decide(score:dict):
    best=("其他",-1.0)
    for lb,sc in score.items():
        if sc>=th.get(lb,0.0) and sc>best[1]:
            best=(lb,sc)
    if best[0]=="其他":
        # 最後補刀：若有次高分但略低於門檻、且與“其他”差距很大，放行以降低“其他”誤判
        non_others=[(lb,sc) for lb,sc in score.items() if lb!="其他"]
        lb2,sc2 = max(non_others, key=lambda x:x[1], default=("其他",0.0))
        if sc2>=0.28 and sc2>=best[1]+0.20:
            best=(lb2,sc2)
    return best[0]

scores=[score_text(t) for t in X]
y_pred=[decide(s) for s in scores]

# 指標
labs=ALLOW
cm={a:{b:0 for b in labs} for a in labs}
for g,p in zip(y,y_pred): cm[g][p]+=1

def prf(lbl):
    TP=cm[lbl][lbl]
    FP=sum(cm[g][lbl] for g in labs if g!=lbl)
    FN=sum(cm[lbl][p] for p in labs if p!=lbl)
    P=TP/(TP+FP) if TP+FP>0 else 0.0
    R=TP/(TP+FN) if TP+FN>0 else 0.0
    F1=(2*P*R)/(P+R) if P+R>0 else 0.0
    return P,R,F1,TP,FP,FN

rows=[]; microTP=microFP=microFN=0
for lb in labs:
    P,R,F1,TP,FP,FN=prf(lb)
    rows.append((lb,P,R,F1,TP,FP,FN))
    microTP+=TP; microFP+=FP; microFN+=FN
macroF=sum(r[2] for r in rows)/len(rows)
microP=microTP/(microTP+microFP) if microTP+microFP>0 else 0.0
microR=microTP/(microTP+microFN) if microTP+microFN>0 else 0.0
microF=(2*microP*microR)/(microP+microR) if microP+microR>0 else 0.0

# 難例導出
from collections import defaultdict
hard=defaultdict(list)
for txt,gt,sc,pd in zip(X,y,scores,y_pred):
    if gt!=pd and len(hard[gt])<40:
        hard[gt].append({"text":txt,"gold":gt,"pred":pd,"scores":sc})
hard_p=EVADIR/"intent_unmatched.v5.jsonl"
with hard_p.open("w",encoding="utf-8") as f:
    for lb in labs:
        for it in hard[lb]:
            f.write(json.dumps(it,ensure_ascii=False)+"\n")

# 報表
md=[]
md.append("# Intent metrics (rules hotfix v5)")
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

md_p=EVADIR/"metrics_intent_rules_hotfix_v5.md"
Path(md_p).write_text("\n".join(md),encoding="utf-8")
print(f"[OK] wrote {md_p}")

# 附到 ONECLICK 摘要
st_dir=ROOT/"reports_auto/status"
if st_dir.exists():
    latest=sorted(st_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
    if latest:
        with latest[0].open("a",encoding="utf-8") as f:
            f.write("\n## Intent metrics (rules hotfix v5)\n")
            f.write(Path(md_p).read_text("utf-8"))
        print(f"[OK] appended metrics to {latest[0].as_posix()]}")
PY

LATEST="$(ls -td reports_auto/eval/* | head -n1)"
echo ">>> Result => $LATEST/metrics_intent_rules_hotfix_v5.md"
sed -n '1,120p' "$LATEST/metrics_intent_rules_hotfix_v5.md" || true
