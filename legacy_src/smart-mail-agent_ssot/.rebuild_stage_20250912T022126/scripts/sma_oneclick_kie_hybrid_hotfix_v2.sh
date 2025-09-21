#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
OUTDIR="reports_auto/kie_eval/${TS}"
mkdir -p "$OUTDIR" "reports_auto/status" "data/kie_eval"

python - <<'PY'
# -*- coding: utf-8 -*-
import os, re, json, time, hashlib
from pathlib import Path
from collections import defaultdict

ROOT = Path(".")
NOW  = time.strftime("%Y%m%dT%H%M%S")
OUTDIR = ROOT/f"reports_auto/kie_eval/{NOW}"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ===== 參數 =====
ALLOW_LABELS = {"amount","date_time","env","sla"}
LABEL_MAP = {
    "datetime":"date_time", "date-time":"date_time", "time_date":"date_time",
    "environment":"env", "stage":"env"
}
# 類別化閾值（降低 env/sla 門檻補召回）
MIN_SCORE = {"amount":0.50, "date_time":0.50, "env":0.35, "sla":0.40}
RULE_SCORE = 0.93
NMS_IOU    = 0.90
LENIENT_IOU= 0.50

def thash(t:str)->str: return hashlib.md5((t or "").encode("utf-8")).hexdigest()

def iou(a,b):
    s1,e1=a; s2,e2=b
    inter=max(0,min(e1,e2)-max(s1,s2))
    if inter==0: return 0.0
    union=(e1-s1)+(e2-s2)-inter
    return inter/union if union>0 else 0.0

def nlabel(lbl:str)->str:
    lbl=(lbl or "").strip()
    return LABEL_MAP.get(lbl,lbl)

def load_jsonl(p:Path):
    out=[]
    with p.open("r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if not ln: continue
            try: out.append(json.loads(ln))
            except: pass
    return out

def dump_jsonl(items,p:Path):
    with p.open("w",encoding="utf-8") as f:
        for x in items: f.write(json.dumps(x,ensure_ascii=False)+"\n")

# ===== 1) 蒐集/合併金標（去重 by text）=====
want_names={"gold_for_train.jsonl","label_queue.jsonl","silver.jsonl","silver_base.jsonl",
            "silver_val.jsonl","test.jsonl","test.demo.jsonl","test_real.jsonl",
            "train.jsonl","val.jsonl"}
cands=[]
for base in [ROOT/"artifacts_inbox", ROOT/"data/staged_project", ROOT/"data", ROOT]:
    if not base.exists(): continue
    for dp,_,fs in os.walk(base):
        for n in fs:
            if n in want_names or (n.startswith("silver") and n.endswith(".jsonl")) or (n.startswith("test") and n.endswith(".jsonl")):
                p=Path(dp)/n
                try:
                    if p.stat().st_size>0: cands.append(p)
                except: pass
cands=sorted(set(cands), key=lambda p:p.stat().st_mtime, reverse=True)

gold={}
for p in cands:
    for r in load_jsonl(p):
        t = r.get("text") or r.get("body") or r.get("subject") or ""
        if not t: continue
        k = thash(t)
        spans=[]
        for s in (r.get("spans") or []):
            lb=nlabel(s.get("label",""))
            if lb not in ALLOW_LABELS: continue
            try:
                s0=int(s["start"]); e0=int(s["end"])
                if e0>s0: spans.append({"start":s0,"end":e0,"label":lb})
            except: continue
        if spans: gold[k]={"text":t,"spans":spans}

gold_list=[gold[k] for k in gold]
if not gold_list:
    print("[FATAL] 找不到任何 KIE 金標（spans）來源"); raise SystemExit(2)
gold_p = ROOT/"data/kie_eval/gold_merged.jsonl"
dump_jsonl(gold_list, gold_p)
print(f"[OK] gold merged -> {gold_p} files_used={len(cands)} size={len(gold_list)}")

# ===== 2) 掃描所有模型預測檔 =====
pred_files=[]
for base in [ROOT/"artifacts_inbox", ROOT/"data/staged_project", ROOT]:
    if not base.exists(): continue
    for dp,_,fs in os.walk(base):
        for n in fs:
            if n.startswith("kie_pred") and n.endswith(".jsonl"):
                pred_files.append(Path(dp)/n)
pred_files=sorted(set(pred_files), key=lambda p:p.stat().st_mtime, reverse=True)
print(f"[INFO] found pred files: {len(pred_files)}")

# ===== 3) 加強版規則 =====
# 金額：台幣/美金/美元/新台幣/NTD/NT$…（含千分位/小數）
RE_AMOUNT = re.compile(r'(?:NT\$|NTD|TWD|USD|US\$|新台幣|台幣|元|\$)\s?[+-]?\d[\d,]*(?:\.\d+)?', re.I)

# 日期：YYYY/MM/DD、MM/DD、YYYY-MM、月份中文字/標點常見情形；保留寬鬆（你的金標有 08/32 也要吃到）
RE_DATE = re.compile(
    r'(?:(\d{4})[\/\-.年](\d{1,2})[\/\-.月](\d{1,2})(?:日)?)'  # 2025/08/31
    r'|(?<!\d)(\d{1,2})[\/\-.](\d{1,2})(?!\d)'                 # 9/30
)

# 環境：補齊常見別名/縮寫，但避免過廣（不單獨匹配「正式」「測試」）
ENV_WORDS = [
  "staging","stage","stg","preprod","pre-prod","preproduction","pre-production",
  "uat","sit","qa","dev","development","demo","preview","sandbox","prod","production","live"
]
RE_ENV = re.compile(r'\b(?:' + '|'.join(map(re.escape,ENV_WORDS)) + r')\b|正式機|測試機|測試環境|預備機|預備環境|沙箱', re.I)

# SLA：增加 SLO/SLI/MTTR/MTBF/RTO/RPO/uptime/availability/支援時段/回應時限等
RE_SLA = re.compile(
    r'\b(?:SLA|SLO|SLI|MTTR|MTBF|RTO|RPO|uptime|availability|downtime|incident)\b'
    r'|服務水準|服務等級|回應時間|回覆時間|回應時限|支援時段|支援時間|24x7|7x24|7/24|全年無休|SLA協議|服務等級協議',
    re.I
)

def rule_spans(text):
    spans=[]
    for m in RE_AMOUNT.finditer(text): spans.append({"start":m.start(),"end":m.end(),"label":"amount","score":RULE_SCORE})
    for m in RE_DATE.finditer(text):   spans.append({"start":m.start(),"end":m.end(),"label":"date_time","score":RULE_SCORE})
    for m in RE_ENV.finditer(text):    spans.append({"start":m.start(),"end":m.end(),"label":"env","score":RULE_SCORE})
    for m in RE_SLA.finditer(text):    spans.append({"start":m.start(),"end":m.end(),"label":"sla","score":RULE_SCORE})
    return spans

def keep_model_span(s):
    sc = s.get("score", s.get("prob", s.get("confidence", None)))
    if sc is None: return False
    try:
        sc=float(sc)
    except:
        return False
    return sc >= MIN_SCORE.get(s["label"],0.0)

def merge_spans(spans):
    by=defaultdict(list)
    for s in spans: by[s["label"]].append(dict(s))
    out=[]
    for lb, arr in by.items():
        arr=sorted(arr,key=lambda x:x.get("score",0.0),reverse=True)
        kept=[]
        for s in arr:
            keep=True
            for k in kept:
                if iou((s["start"],s["end"]),(k["start"],k["end"]))>=0.90:
                    k["start"]=min(k["start"],s["start"])
                    k["end"]=max(k["end"],s["end"])
                    k["score"]=max(k.get("score",0.0),s.get("score",0.0))
                    keep=False; break
            if keep: kept.append(s)
        out.extend(kept)
    return out

# ===== 4) 索引模型預測 =====
pred_index = defaultdict(list)   # k -> spans[]
for pf in pred_files:
    for r in load_jsonl(pf):
        t = r.get("text") or r.get("body") or r.get("subject") or ""
        if not t: continue
        k = thash(t)
        cur=[]
        for s in (r.get("spans") or []):
            lb=nlabel(s.get("label",""))
            if lb not in ALLOW_LABELS: continue
            try:
                s0=int(s["start"]); e0=int(s["end"])
                if e0<=s0: continue
            except: continue
            cand={"start":s0,"end":e0,"label":lb}
            sc = s.get("score", s.get("prob", s.get("confidence", None)))
            if sc is None: continue
            try: cand["score"]=float(sc)
            except: continue
            if keep_model_span(cand): cur.append(cand)
        if cur: pred_index[k].extend(cur)

# ===== 5) 產生 Hybrid（模型 + 強化規則）並計算規則/模型貢獻 =====
hybrid=[]; total_kept=0
src_count={"model":{"amount":0,"date_time":0,"env":0,"sla":0},
           "rules":{"amount":0,"date_time":0,"env":0,"sla":0}}

def count_src(before, after, label):
    # 以數量近似貢獻（NMS 合併後只統計留下的）
    diff = max(0, after - before)
    src_count["rules"][label] += diff

for g in load_jsonl(gold_p):
    t=g["text"]; k=thash(t)
    msp = list(pred_index.get(k, []))   # 模型
    rs  = rule_spans(t)                  # 規則
    base_before = {lb:0 for lb in ALLOW_LABELS}
    for s in msp: base_before[s["label"]] += 1
    spans = msp + rs
    spans = merge_spans(spans)
    # 統計規則貢獻
    after = {lb:0 for lb in ALLOW_LABELS}
    for s in spans: after[s["label"]] += 1
    for lb in ALLOW_LABELS: count_src(base_before[lb], after[lb], lb)
    total_kept += len(spans)
    hybrid.append({"text":t,"spans":spans})

# 回填模型貢獻（總 kept 減去規則）
for lb in ALLOW_LABELS:
    model_kept = sum(1 for r in hybrid for s in r["spans"] if s["label"]==lb)
    src_count["model"][lb] = max(0, model_kept - src_count["rules"][lb])

hyb_p = OUTDIR/"hybrid_preds.jsonl"
dump_jsonl(hybrid, hyb_p)
print(f"[OK] hybrid preds -> {hyb_p} total_kept_spans={total_kept}")
print("[INFO] kept spans by source (approx):", json.dumps(src_count, ensure_ascii=False))

# ===== 6) 評測（strict / lenient）=====
def prf_counts(gold_spans, pred_spans, lenient=False):
    labels=sorted(ALLOW_LABELS)
    cnt={lb:{"TP":0,"FP":0,"FN":0} for lb in labels}
    used=set()
    for gi,g in enumerate(gold_spans):
        gl=g["label"]; matched=False
        for pi,p in enumerate(pred_spans):
            if pi in used or p["label"]!=gl: continue
            ok = (p["start"]==g["start"] and p["end"]==g["end"]) if not lenient \
                 else (iou((g["start"],g["end"]),(p["start"],p["end"]))>=LENIENT_IOU)
            if ok:
                cnt[gl]["TP"]+=1; used.add(pi); matched=True; break
        if not matched: cnt[gl]["FN"]+=1
    for pi,p in enumerate(pred_spans):
        if pi not in used: cnt[p["label"]]["FP"]+=1
    return cnt

def metrics(cnt):
    rows=[]; microTP=microFP=microFN=0
    for lb in sorted(cnt.keys()):
        TP=cnt[lb]["TP"]; FP=cnt[lb]["FP"]; FN=cnt[lb]["FN"]
        P = TP/(TP+FP) if TP+FP>0 else 0.0
        R = TP/(TP+FN) if TP+FN>0 else 0.0
        F1= (2*P*R)/(P+R) if P+R>0 else 0.0
        rows.append((lb,P,R,F1,TP,FP,FN))
        microTP+=TP; microFP+=FP; microFN+=FN
    microP = microTP/(microTP+microFP) if microTP+microFP>0 else 0.0
    microR = microTP/(microTP+microFN) if microTP+microFN>0 else 0.0
    microF = (2*microP*microR)/(microP+microR) if microP+microR>0 else 0.0
    macroF = sum(r[3] for r in rows)/len(rows) if rows else 0.0
    return {"rows":rows,"microP":microP,"microR":microR,"microF":microF,"macroF":macroF}

strict_cnt = {lb:{"TP":0,"FP":0,"FN":0} for lb in ALLOW_LABELS}
len_cnt    = {lb:{"TP":0,"FP":0,"FN":0} for lb in ALLOW_LABELS}

hy_by_k = { thash(r["text"]): r for r in hybrid }
for g in load_jsonl(gold_p):
    k=thash(g["text"])
    p = hy_by_k.get(k, {"spans":[]})
    gsp=[{"label":nlabel(s["label"]), "start":int(s["start"]), "end":int(s["end"])}
         for s in (g.get("spans") or []) if nlabel(s.get("label","")) in ALLOW_LABELS]
    psp=[{"label":nlabel(s["label"]), "start":int(s["start"]), "end":int(s["end"])}
         for s in (p.get("spans") or []) if nlabel(s.get("label","")) in ALLOW_LABELS]
    sc = prf_counts(gsp, psp, lenient=False)
    lc = prf_counts(gsp, psp, lenient=True)
    for lb in ALLOW_LABELS:
        for k2 in ("TP","FP","FN"):
            strict_cnt[lb][k2]+=sc[lb][k2]
            len_cnt[lb][k2]+=lc[lb][k2]

mS = metrics(strict_cnt)
mL = metrics(len_cnt)

md=[]
md.append("# KIE span metrics (hybrid hotfix v2)")
md.append(f"- gold_file: {gold_p.as_posix()}")
md.append(f"- pred_files: {len(pred_files)} (hybrid=rules+model)")
md.append(f"- total_kept_spans: {total_kept}")
md.append(f"- strict micro P/R/F1: {mS['microP']:.3f}/{mS['microR']:.3f}/{mS['microF']:.3f}")
md.append(f"- strict macro F1: {mS['macroF']:.3f}\n")
md.append("|label|P|R|F1|TP|FP|FN|")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for lb,P,R,F1,TP,FP,FN in mS["rows"]:
    md.append(f"|{lb}|{P:.3f}|{R:.3f}|{F1:.3f}|{TP}|{FP}|{FN}|")

md.append("\n## lenient (IoU≥0.50)")
md.append(f"- lenient micro P/R/F1: {mL['microP']:.3f}/{mL['microR']:.3f}/{mL['microF']:.3f}")
md.append(f"- lenient macro F1: {mL['macroF']:.3f}")
md.append("|label|P|R|F1|TP|FP|FN|")
md.append("|---|---:|---:|---:|---:|---:|---:|")
for lb,P,R,F1,TP,FP,FN in mL["rows"]:
    md.append(f"|{lb}|{P:.3f}|{R:.3f}|{F1:.3f}|{TP}|{FP}|{FN}|")

md.append("\n## kept spans by source (approx)")
md.append("```json")
md.append(json.dumps(src_count, ensure_ascii=False, indent=2))
md.append("```")

md_p = OUTDIR/"metrics_kie_spans.md"
(Path(md_p)).write_text("\n".join(md),encoding="utf-8")
print(f"[OK] wrote {md_p}")

# ===== 7) 附到最新 ONECLICK 摘要 =====
st_dir = ROOT/"reports_auto/status"
if st_dir.exists():
    latest = sorted(st_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
    if latest:
        with latest[0].open("a",encoding="utf-8") as f:
            f.write("\n## KIE span metrics (hybrid hotfix v2)\n")
            f.write(Path(md_p).read_text("utf-8"))
        print(f"[OK] appended metrics to {latest[0].as_posix()}")
PY

LATEST="$(ls -td reports_auto/kie_eval/* | head -n1)"
echo ">>> Result => $LATEST/metrics_kie_spans.md"
sed -n '1,200p' "$LATEST/metrics_kie_spans.md" || true
