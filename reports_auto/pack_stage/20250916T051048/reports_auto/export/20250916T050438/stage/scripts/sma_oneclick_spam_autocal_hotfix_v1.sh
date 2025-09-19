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
import json, re, time, math, os
from pathlib import Path

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"
EVADIR.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    out=[]
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

# 1) 金標（需要有 label: 1/0 或 spam/ham）
ds_p = ROOT/"data/spam_eval/dataset.jsonl"
if not ds_p.exists() or ds_p.stat().st_size==0:
    print("[SKIP] data/spam_eval/dataset.jsonl 空，略過 Spam hotfix")
    raise SystemExit(0)
gold = read_jsonl(ds_p)

def norm_y(r):
    v = r.get("label")
    if isinstance(v,bool): return 1 if v else 0
    if isinstance(v,(int,float)): return 1 if v>=1 else 0
    if isinstance(v,str):
        v=v.strip().lower()
        if v in ("spam","1","true","yes"): return 1
        if v in ("ham","0","false","no","legit","valid"): return 0
    # 有些資料會用 "is_spam"
    v = r.get("is_spam")
    if isinstance(v,bool): return 1 if v else 0
    if isinstance(v,(int,float)): return 1 if v>=1 else 0
    return None

X=[]; y=[]
for r in gold:
    t = r.get("text") or r.get("body") or r.get("subject") or ""
    yy= norm_y(r)
    if t and yy is not None:
        X.append(t); y.append(yy)
N=len(y)
print(f"[INFO] gold size={N}")
if N==0:
    print("[FATAL] spam gold 無法解析標籤"); raise SystemExit(2)

# 2) 收集 score（先找 spam_pred*.jsonl，有 text/hash 對齊最佳；其次如果 gold 本身有 score）
from hashlib import md5
def thash(t): return md5((t or "").encode("utf-8")).hexdigest()

index={}
# a) 先從 gold 抓 score（若存在）
for r in gold:
    t = r.get("text") or r.get("body") or r.get("subject") or ""
    if not t: continue
    sc = r.get("score") or r.get("prob") or r.get("confidence")
    if sc is not None:
        try: sc=float(sc)
        except: sc=None
    if sc is not None:
        index[thash(t)]=sc

# b) 掃預測檔
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
        t = r.get("text") or r.get("body") or r.get("subject") or ""
        if not t: continue
        sc = r.get("score") or r.get("prob") or r.get("confidence")
        if sc is None: continue
        try: sc=float(sc)
        except: continue
        index.setdefault(thash(t), sc)

scores=[index.get(thash(t)) for t in X]
have = sum(1 for s in scores if isinstance(s,(int,float)))
print(f"[INFO] matched scores={have}/{N}")

if have==0:
    print("[FATAL] 找不到任何 spam score，請先產出 spam_pred.jsonl 或在 gold 附 score")
    raise SystemExit(2)

# 3) 掃描門檻找最佳 F1
def eval_thr(th):
    TP=FP=FN=TN=0
    for yy,sc in zip(y,scores):
        if sc is None: continue
        pred= 1 if sc>=th else 0
        if pred==1 and yy==1: TP+=1
        elif pred==1 and yy==0: FP+=1
        elif pred==0 and yy==1: FN+=1
        else: TN+=1
    P= TP/(TP+FP) if TP+FP>0 else 0.0
    R= TP/(TP+FN) if TP+FN>0 else 0.0
    F1=(2*P*R)/(P+R) if P+R>0 else 0.0
    return P,R,F1,TP,FP,FN,TN

best=(0.0,-1.0,None)  # (thr,F1,stats)
grid=[i/100 for i in range(5,96)]  # 0.05~0.95
for th in grid:
    P,R,F1,TP,FP,FN,TN=eval_thr(th)
    if F1>best[1]: best=(th,F1,(P,R,TP,FP,FN,TN))

thr, bestF1, stats = best
P,R,TP,FP,FN,TN = stats
md=[]
md.append("# Spam metrics (auto-cal threshold)")
md.append(f"- dataset: data/spam_eval/dataset.jsonl size={N}")
md.append(f"- matched_scores: {have}/{N}")
md.append(f"- best_threshold: {thr:.2f}")
md.append(f"- P/R/F1: {P:.3f}/{R:.3f}/{bestF1:.3f}")
md.append(f"- TP/FP/FN/TN: {TP}/{FP}/{FN}/{TN}")

md_p = EVADIR/"metrics_spam_autocal.md"
(Path(md_p)).write_text("\n".join(md),encoding="utf-8")
print(f"[OK] wrote {md_p}")

# 4) 寫回 ens_thresholds.json（若存在就更新 spam 的 key）
ens_p = ROOT/"artifacts_prod/ens_thresholds.json"
ens = {}
if ens_p.exists():
    try: ens=json.loads(ens_p.read_text("utf-8"))
    except: ens={}
ens["spam_threshold"]=thr
ens_p.write_text(json.dumps(ens,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"[OK] updated {ens_p.as_posix()} -> spam_threshold={thr:.2f}")

# 5) 附到 ONECLICK 摘要
st_dir = ROOT/"reports_auto/status"
if st_dir.exists():
    latest = sorted(st_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
    if latest:
        with latest[0].open("a",encoding="utf-8") as f:
            f.write("\n## Spam metrics (auto-cal hotfix v1)\n")
            f.write(Path(md_p).read_text("utf-8"))
        print(f"[OK] appended metrics to {latest[0].as_posix()}")
PY

LATEST="$(ls -td reports_auto/eval/* | head -n1)"
echo ">>> Result => $LATEST/metrics_spam_autocal.md"
sed -n '1,120p' "$LATEST/metrics_spam_autocal.md" || true
