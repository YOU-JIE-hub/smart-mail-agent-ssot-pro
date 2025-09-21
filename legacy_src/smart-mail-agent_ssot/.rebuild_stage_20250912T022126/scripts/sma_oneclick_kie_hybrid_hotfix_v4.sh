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
import os, re, json, time, hashlib, unicodedata
from pathlib import Path
from collections import defaultdict

ROOT   = Path(".")
NOW    = time.strftime("%Y%m%dT%H%M%S")
OUTDIR = ROOT/f"reports_auto/kie_eval/{NOW}"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ===== Params =====
ALLOW_LABELS = {"amount","date_time","env","sla"}
LABEL_MAP = {
    "datetime":"date_time","date-time":"date_time","time_date":"date_time","date":"date_time","time":"date_time",
    "environment":"env","stage":"env","stg":"env","uat_env":"env","sit_env":"env",
    "金額":"amount","日期":"date_time","環境":"env","SLA":"sla","sla條款":"sla"
}
# 類別化閾值（放寬 env/sla）
MIN_SCORE = {"amount":0.50,"date_time":0.50,"env":0.25,"sla":0.20}
DEFAULT_MODEL_SCORE = 0.60
NMS_IOU     = 0.90
LENIENT_IOU = 0.50

PUNCT = " \t\r\n　。、，；：:,.!?！？（）()[]【】「」『』…‧・/\\"

def thash(t:str)->str:
    return hashlib.md5((t or "").encode("utf-8")).hexdigest()

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

# ===== 1) Merge golds =====
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
    print("[FATAL] 找不到任何含 spans 的金標來源"); raise SystemExit(2)
gold_p = ROOT/"data/kie_eval/gold_merged.jsonl"
dump_jsonl(gold_list, gold_p)
print(f"[OK] gold merged -> {gold_p} files_used={len(cands)} size={len(gold_list)}")

# ===== 2) Collect model preds =====
pred_files=[]
for base in [ROOT/"artifacts_inbox", ROOT/"data/staged_project", ROOT]:
    if not base.exists(): continue
    for dp,_,fs in os.walk(base):
        for n in fs:
            if n.startswith("kie_pred") and n.endswith(".jsonl"):
                pred_files.append(Path(dp)/n)
pred_files=sorted(set(pred_files), key=lambda p:p.stat().st_mtime, reverse=True)
print(f"[INFO] found pred files: {len(pred_files)}")

# ===== 3) Rules =====
RE_AMOUNT = re.compile(r'(?:NT\$|NTD|TWD|USD|US\$|新台幣|台幣|元|\$)\s?[+-]?\d[\d,]*(?:\.\d+)?', re.I)
RE_DATE = re.compile(
    r'(?:(\d{4})[\/\-.年](\d{1,2})[\/\-.月](\d{1,2})(?:日)?)'   # 2025/08/31
    r'|(?<!\d)(\d{1,2})[\/\-.](\d{1,2})(?!\d)'                  # 9/30
)
ENV_WORDS = [
  "staging","stage","stg","preprod","pre-prod","preproduction","pre-production",
  "uat","sit","qa","dev","development","demo","preview","sandbox","prod","production","live"
]
RE_ENV = re.compile(
    r'\b(?:' + '|'.join(map(re.escape,ENV_WORDS)) + r')\b'
    r'|正式機|正式環境|測試機|測試環境|預備機|預備環境|沙箱', re.I)

SLA_CORE = r'(?:[SＳ]\s*[/\-＿﹣–—_]?\s*[LＬ]\s*[/\-＿﹣–—_]?\s*[AＡ])'
RE_SLA = re.compile(
    rf'{SLA_CORE}'
    r'|SLO|SLI|MTTR|MTBF|RTO|RPO|uptime|availability|downtime|incident'
    r'|服務水準|服務等級|服務等級協議|服務水準協議|服務等級協定|服務水準協定|回應時間|回覆時間|回應時限|支援時段|支援時間|全年無休|24x7|7x24|7/24',
    re.I
)
RE_SLA_TOKEN = re.compile(SLA_CORE, re.I)  # 用來在長片段中縮窗到「SLA/ＳＬＡ」

def strip_span(text, s0, e0):
    # 去除前後空白與標點
    while s0<e0 and text[s0] in PUNCT: s0+=1
    while e0>s0 and text[e0-1] in PUNCT: e0-=1
    return s0,e0

def shrink_label_window(text, s0, e0, label):
    frag = text[s0:e0]
    # 將全形轉半形用於搜索，計算偏移
    norm = unicodedata.normalize("NFKC", frag)
    if label=="sla":
        m = RE_SLA_TOKEN.search(norm)
        if m:
            # 找到 token 後把範圍收斂到該 token（避免抓到「文件與 SLA 說明」太長）
            rel_start, rel_end = m.start(), m.end()
            # 反推原字串索引（簡化：用相同長度對齊，不完美但對 ASCII/全形混排夠用）
            s0 = s0 + rel_start
            e0 = s0 + (rel_end - rel_start)
    # 去頭尾標點
    s0,e0 = strip_span(text, s0, e0)
    return s0,e0

def rule_spans(text):
    out=[]
    for m in RE_AMOUNT.finditer(text):
        s0,e0 = strip_span(text, m.start(), m.end())
        out.append({"start":s0,"end":e0,"label":"amount","score":0.98,"src":"rule"})
    for m in RE_DATE.finditer(text):
        s0,e0 = strip_span(text, m.start(), m.end())
        out.append({"start":s0,"end":e0,"label":"date_time","score":0.98,"src":"rule"})
    for m in RE_ENV.finditer(text):
        s0,e0 = strip_span(text, m.start(), m.end())
        out.append({"start":s0,"end":e0,"label":"env","score":0.98,"src":"rule"})
    for m in RE_SLA.finditer(text):
        s0,e0 = shrink_label_window(text, m.start(), m.end(), "sla")
        out.append({"start":s0,"end":e0,"label":"sla","score":0.98,"src":"rule"})
    return out

def keep_model_span(s):
    sc = s.get("score", s.get("prob", s.get("confidence", None)))
    if sc is None:
        sc = DEFAULT_MODEL_SCORE
    try:
        sc = float(sc)
    except:
        sc = DEFAULT_MODEL_SCORE
    return sc >= MIN_SCORE.get(s["label"],0.0), float(sc)

def merge_spans(spans):
    by=defaultdict(list)
    for s in spans:
        by[s["label"]].append(dict(s))
    out=[]
    for lb, arr in by.items():
        arr=sorted(arr,key=lambda x:x.get("score",0.0),reverse=True)
        kept=[]
        for s in arr:
            keep=True
            for k in kept:
                if iou((s["start"],s["end"]),(k["start"],k["end"]))>=NMS_IOU:
                    k["start"]=min(k["start"],s["start"])
                    k["end"]=max(k["end"],s["end"])
                    if s.get("score",0.0) > k.get("score",0.0):
                        k["score"]=s.get("score",0.0)
                        k["src"]=s.get("src",k.get("src","mix"))
                    else:
                        if k.get("src")!=s.get("src"): k["src"]="mix"
                    keep=False; break
            if keep: kept.append(s)
        out.extend(kept)
    return out

# ===== 4) Index model predictions =====
pred_index = defaultdict(list)
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
            ok,score = keep_model_span({**s,"label":lb})
            if not ok: continue
            # 縮窗與去標點
            s0,e0 = shrink_label_window(t, s0, e0, lb) if lb in ("sla","env") else strip_span(t, s0, e0)
            cur.append({"start":s0,"end":e0,"label":lb,"score":score,"src":"model"})
        if cur: pred_index[k].extend(cur)

# ===== 5) Build hybrid & count contributions =====
hybrid=[]; total_kept=0
src_count={"model":{"amount":0,"date_time":0,"env":0,"sla":0},
           "rule" :{"amount":0,"date_time":0,"env":0,"sla":0},
           "mix"  :{"amount":0,"date_time":0,"env":0,"sla":0}}

for g in load_jsonl(gold_p):
    t=g["text"]; k=thash(t)
    msp = list(pred_index.get(k, []))
    rs  = rule_spans(t)
    spans = merge_spans(msp + rs)
    total_kept += len(spans)
    for s in spans:
        src = s.get("src","model")
        src_count.setdefault(src, {lb:0 for lb in ALLOW_LABELS})
        src_count[src][s["label"]] = src_count[src].get(s["label"],0) + 1
    hybrid.append({"text":t,"spans":spans})

hyb_p = OUTDIR/"hybrid_preds.jsonl"
dump_jsonl(hybrid, hyb_p)
print(f"[OK] hybrid preds -> {hyb_p} total_kept_spans={total_kept}")
print("[INFO] kept spans by source:", json.dumps(src_count, ensure_ascii=False))

# ===== 6) Eval =====
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
md.append("# KIE span metrics (hybrid hotfix v4)")
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

md.append("\n## kept spans by source (model / rule / mix)")
md.append("```json")
md.append(json.dumps(src_count, ensure_ascii=False, indent=2))
md.append("```")

# 未命中的金標（各標籤 <=20 範例）
hard = {lb:[] for lb in ALLOW_LABELS}
for g in load_jsonl(gold_p):
    k=thash(g["text"]); p=hy_by_k.get(k,{"spans":[]})
    for s in g["spans"]:
        lb=nlabel(s["label"])
        if lb not in ALLOW_LABELS: continue
        matched=False
        for ps in p["spans"]:
            if ps["label"]!=lb: continue
            if iou((s["start"],s["end"]),(ps["start"],ps["end"]))>=LENIENT_IOU:
                matched=True; break
        if not matched and len(hard[lb])<20:
            hard[lb].append({"text":g["text"],"gold":s,"pred":[ps for ps in p["spans"] if ps["label"]==lb]})
dump_jsonl([{"label":lb,"items":hard[lb]} for lb in ALLOW_LABELS], OUTDIR/"unmatched_examples.jsonl")
md.append(f"\n- dumped unmatched examples -> { (OUTDIR/'unmatched_examples.jsonl').as_posix() }")

md_p = OUTDIR/"metrics_kie_spans.md"
(Path(md_p)).write_text("\n".join(md),encoding="utf-8")
print(f"[OK] wrote {md_p}")

# 附到 ONECLICK 摘要
st_dir = ROOT/"reports_auto/status"
if st_dir.exists():
    latest = sorted(st_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
    if latest:
        with latest[0].open("a",encoding="utf-8") as f:
            f.write("\n## KIE span metrics (hybrid hotfix v4)\n")
            f.write(Path(md_p).read_text("utf-8"))
        print(f"[OK] appended metrics to {latest[0].as_posix()}")
PY

LATEST="$(ls -td reports_auto/kie_eval/* | head -n1)"
echo ">>> Result => $LATEST/metrics_kie_spans.md"
sed -n '1,200p' "$LATEST/metrics_kie_spans.md" || true
echo ">>> Unmatched examples (path): $LATEST/unmatched_examples.jsonl"
