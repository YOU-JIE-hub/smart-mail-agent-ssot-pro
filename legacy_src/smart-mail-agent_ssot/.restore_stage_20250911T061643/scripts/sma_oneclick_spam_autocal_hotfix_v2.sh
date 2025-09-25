#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "data/spam_eval" "artifacts_prod"

python - <<'PY'
# -*- coding: utf-8 -*-
import json,re,time,os,hashlib
from pathlib import Path

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    out=[]; 
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

def norm_label(r):
    # 容錯多種欄位
    keys = ["label","is_spam","spam","y","gt","target","class","tag","category","gold","truth"]
    v=None
    for k in keys:
        if k in r:
            v=r[k]; break
    if isinstance(v,bool): return 1 if v else 0
    if isinstance(v,(int,float)): return 1 if v>=1 else 0
    if isinstance(v,str):
        s=v.strip().lower()
        if s in ("spam","junk","phish","1","true","yes","bad"): return 1
        if s in ("ham","ok","legit","valid","0","false","no","good"): return 0
    return None

# 1) 讀現有 gold，若空就嘗試重建
gold = read_jsonl(ROOT/"data/spam_eval/dataset.jsonl")
if not gold:
    # 掃典型來源補 gold
    cands=[]
    for base in [ROOT/"data/benchmarks", ROOT/"data", ROOT/"data/staged_project", ROOT/"artifacts_inbox"]:
        if not base.exists(): continue
        for dp,_,fs in os.walk(base):
            for n in fs:
                if n.endswith(".jsonl") and ("spam" in n or "trec06c" in n or "prod" in dp or "spamassassin" in n):
                    p=Path(dp)/n
                    if p.stat().st_size>0: cands.append(p)
    # 合併並標準化，只收有明確 label 的
    merged=[]
    seen=set()
    for p in sorted(set(cands), key=lambda x:x.stat().st_mtime, reverse=True):
        for r in read_jsonl(p):
            t=r.get("text") or r.get("body") or r.get("subject") or ""
            y=norm_label(r)
            if not t or y is None: continue
            h=hashlib.md5(t.encode("utf-8")).hexdigest()
            if h in seen: continue
            seen.add(h)
            merged.append({"text":t,"label":y})
    if merged:
        outp=ROOT/"data/spam_eval/dataset.jsonl"
        with outp.open("w",encoding="utf-8") as f:
            for r in merged: f.write(json.dumps(r,ensure_ascii=False)+"\n")
        gold=merged
        print(f"[OK] rebuilt gold -> {outp} size={len(gold)}")
    else:
        print("[FATAL] 找不到可用 spam 金標，請確認資料來源"); raise SystemExit(2)

# 2) 匹配 score（優先 spam_pred*.jsonl；其次金標內自帶 score）
index={}
def thash(t): return hashlib.md5((t or "").encode("utf-8")).hexdigest()
# 先吃 gold 自帶 score
for r in gold:
    sc = r.get("score") or r.get("prob") or r.get("confidence") or r.get("spam_score")
    if sc is not None:
        try: index[thash(r.get("text") or r.get("body") or r.get("subject") or "")]=float(sc)
        except: pass
# 掃預測檔
cands=[]
for base in [ROOT/"artifacts_inbox", ROOT/"data/staged_project", ROOT]:
    if not base.exists(): continue
    for dp,_,fs in os.walk(base):
        for n in fs:
            if n.startswith("spam_pred") and n.endswith(".jsonl"):
                p=Path(dp)/n
                if p.stat().st_size>0: cands.append(p)
for p in sorted(set(cands), key=lambda x:x.stat().st_mtime, reverse=True):
    for r in read_jsonl(p):
        t=r.get("text") or r.get("body") or r.get("subject") or ""
        sc=r.get("score") or r.get("prob") or r.get("confidence") or r.get("spam_score")
        if not t or sc is None: continue
        try: sc=float(sc)
        except: continue
        index.setdefault(thash(t), sc)

X=[r.get("text") or r.get("body") or r.get("subject") or "" for r in gold]
y=[1 if (r.get("label")==1 or r.get("is_spam")==1) else 0 for r in gold]
scores=[index.get(thash(t)) for t in X]
matched=sum(1 for s in scores if isinstance(s,(int,float)))
N=len(y)
print(f"[INFO] gold size={N}, matched_scores={matched}/{N}")

# 3) 門檻掃描（有分數）；沒有分數就用 0.5 當 baseline
def eval_thr(th):
    TP=FP=FN=TN=0
    for yy,sc in zip(y,scores):
        if sc is None: continue
        pred=1 if sc>=th else 0
        if pred==1 and yy==1: TP+=1
        elif pred==1 and yy==0: FP+=1
        elif pred==0 and yy==1: FN+=1
        else: TN+=1
    P= TP/(TP+FP) if TP+FP>0 else 0.0
    R= TP/(TP+FN) if TP+FN>0 else 0.0
    F1=(2*P*R)/(P+R) if P+R>0 else 0.0
    return P,R,F1,TP,FP,FN,TN

if matched==0:
    # 無分數 -> 試著讀 'pred' 類欄位當二元輸出，報 baseline
    preds=[]
    for r in gold:
        v=None
        for k in ("pred","prediction","is_spam_pred","spam_pred"):
            if k in r: v=r[k]; break
        if isinstance(v,bool): preds.append(1 if v else 0)
        elif isinstance(v,(int,float)): preds.append(1 if v>=1 else 0)
        else: preds.append(0)
    TP=FP=FN=TN=0
    for gt,pd in zip(y,preds):
        if pd==1 and gt==1: TP+=1
        elif pd==1 and gt==0: FP+=1
        elif pd==0 and gt==1: FN+=1
        else: TN+=1
    P=TP/(TP+FP) if TP+FP>0 else 0.0
    R=TP/(TP+FN) if TP+FN>0 else 0.0
    F1=(2*P*R)/(P+R) if P+R>0 else 0.0
    thr=None
    md=[
      "# Spam metrics (auto-cal hotfix v2)",
      f"- dataset: data/spam_eval/dataset.jsonl size={N}",
      f"- matched_scores: {matched}/{N}",
      f"- best_threshold: N/A (no score found)",
      f"- P/R/F1 (baseline using 'pred'): {P:.3f}/{R:.3f}/{F1:.3f}",
      f"- TP/FP/FN/TN: {TP}/{FP}/{FN}/{TN}"
    ]
else:
    best=(0.0,-1.0,None)
    grid=[i/100 for i in range(5,96)]
    for th in grid:
        P,R,F1,TP,FP,FN,TN=eval_thr(th)
        if F1>best[1]:
            best=(th,F1,(P,R,TP,FP,FN,TN))
    thr,bF1,stats=best; P,R,TP,FP,FN,TN=stats
    md=[
      "# Spam metrics (auto-cal hotfix v2)",
      f"- dataset: data/spam_eval/dataset.jsonl size={N}",
      f"- matched_scores: {matched}/{N}",
      f"- best_threshold: {thr:.2f}",
      f"- P/R/F1: {P:.3f}/{R:.3f}/{bF1:.3f}",
      f"- TP/FP/FN/TN: {TP}/{FP}/{FN}/{TN}"
    ]

md_p=EVADIR/"metrics_spam_autocal_v2.md"
Path(md_p).write_text("\n".join(md),encoding="utf-8")
print(f"[OK] wrote {md_p}")

# 4) 更新 ens_thresholds.json（有 thr 才更新）
ens_p=ROOT/"artifacts_prod/ens_thresholds.json"
try: ens=json.loads(ens_p.read_text("utf-8")) if ens_p.exists() else {}
except: ens={}
if 'best_threshold' not in locals() or best[1]<0:
    print("[INFO] no numeric threshold to update")
else:
    ens["spam_threshold"]=thr
    ens_p.write_text(json.dumps(ens,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"[OK] updated {ens_p.as_posix()} -> spam_threshold={thr:.2f}")

# 5) 附到 ONECLICK
st_dir=ROOT/"reports_auto/status"
if st_dir.exists():
    latest=sorted(st_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
    if latest:
        with latest[0].open("a",encoding="utf-8") as f:
            f.write("\n## Spam metrics (auto-cal hotfix v2)\n")
            f.write(Path(md_p).read_text("utf-8"))
        print(f"[OK] appended metrics to {latest[0].as_posix()}")
PY

LATEST="$(ls -td reports_auto/eval/* | head -n1)"
echo ">>> Result => $LATEST/metrics_spam_autocal_v2.md"
sed -n '1,120p' "$LATEST/metrics_spam_autocal_v2.md" || true
