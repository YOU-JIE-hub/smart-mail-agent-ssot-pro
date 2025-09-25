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

# ========== 參數 ==========
ALLOW_LABELS = {"amount","date_time","env","sla"}
LABEL_MAP = {
    "datetime":"date_time",
    "date-time":"date_time",
    "time_date":"date_time",
    "environment":"env",
    "stage":"env",
}
MIN_SCORE = {"amount":0.50, "date_time":0.50, "env":0.50, "sla":0.50}
RULE_SCORE = 0.93
NMS_IOU = 0.90
LENIENT_IOU = 0.50

def text_hash(t:str)->str:
    return hashlib.md5((t or "").encode("utf-8")).hexdigest()

def iou(a,b):
    s1,e1=a; s2,e2=b
    inter=max(0,min(e1,e2)-max(s1,s2))
    if inter==0: return 0.0
    union=(e1-s1)+(e2-s2)-inter
    return inter/union if union>0 else 0.0

def norm_label(lbl:str)->str:
    lbl=(lbl or "").strip()
    lbl=LABEL_MAP.get(lbl,lbl)
    return lbl

def load_jsonl(p:Path):
    out=[]
    with p.open("r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if not ln: continue
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out

def dump_jsonl(items,p:Path):
    with p.open("w",encoding="utf-8") as f:
        for x in items:
            f.write(json.dumps(x,ensure_ascii=False)+"\n")

# ---------- 1) 蒐集金標並合併 ----------
want_names={"gold_for_train.jsonl","label_queue.jsonl","silver.jsonl","silver_base.jsonl",
            "silver_val.jsonl","test.jsonl","test.demo.jsonl","test_real.jsonl",
            "train.jsonl","val.jsonl"}
gold_candidates=[]
for base in [ROOT/"artifacts_inbox", ROOT/"data/staged_project", ROOT/"data", ROOT]:
    if not base.exists(): continue
    for dp,_,fs in os.walk(base):
        for n in fs:
            if n in want_names or (n.startswith("silver") and n.endswith(".jsonl")) or (n.startswith("test") and n.endswith(".jsonl")):
                p=Path(dp)/n
                try:
                    if p.stat().st_size>0:
                        gold_candidates.append(p)
                except Exception:
                    pass

gold_candidates = sorted(set(gold_candidates), key=lambda p:p.stat().st_mtime, reverse=True)
gold_merge={}
for p in gold_candidates:
    for r in load_jsonl(p):
        t = r.get("text") or r.get("body") or r.get("subject") or ""
        k = text_hash(t)
        spans=[]
        for s in (r.get("spans") or []):
            lb = norm_label(s.get("label",""))
            if lb in ALLOW_LABELS:
                try:
                    s0=int(s["start"]); e0=int(s["end"])
                    if e0>s0: spans.append({"start":s0,"end":e0,"label":lb})
                except Exception:
                    continue
        if spans:
            gold_merge[k]={"text":t,"spans":spans}

gold_list=[gold_merge[k] for k in gold_merge]
if not gold_list:
    print("[FATAL] 找不到任何 KIE 金標（spans 版）來源。請確認 gold/silver/test*.jsonl 是否在倉內。")
    raise SystemExit(2)

gold_p = ROOT/"data/kie_eval/gold_merged.jsonl"
dump_jsonl(gold_list, gold_p)
print(f"[OK] gold merged -> {gold_p} files_used={len(gold_candidates)} size={len(gold_list)}")

# ---------- 2) 掃描所有模型預測檔 ----------
pred_files=[]
for base in [ROOT/"artifacts_inbox", ROOT/"data/staged_project", ROOT]:
    if not base.exists(): continue
    for dp,_,fs in os.walk(base):
        for n in fs:
            if n.startswith("kie_pred") and n.endswith(".jsonl"):
                pred_files.append(Path(dp)/n)
pred_files=sorted(set(pred_files), key=lambda p:p.stat().st_mtime, reverse=True)
print(f"[INFO] found pred files: {len(pred_files)}")

# ---------- 規則抽取 ----------
RE_AMOUNT = re.compile(r'(?:NT\$|TWD|USD|\$)\s?[\d][\d,\.]*', re.I)
RE_DATE   = re.compile(r'(?:(?P<y>\d{4})[\/\-年\.](?P<m>\d{1,2})[\/\-月\.](?P<d>\d{1,2})(?:日)?)|(?<!\d)(?P<m2>\d{1,2})[\/\-](?P<d2>\d{1,2})(?!\d)')
RE_ENV    = re.compile(r'\b(prod(?:uction)?|staging|uat|dev)\b|正式機|測試機', re.I)
RE_SLA    = re.compile(r'\bSLA\b|uptime|availability|可用性|服務水準|回應時間', re.I)
def rule_spans(text):
    spans=[]
    for m in RE_AMOUNT.finditer(text): spans.append({"start":m.start(),"end":m.end(),"label":"amount","score":RULE_SCORE})
    for m in RE_DATE.finditer(text):   spans.append({"start":m.start(),"end":m.end(),"label":"date_time","score":RULE_SCORE})
    for m in RE_ENV.finditer(text):    spans.append({"start":m.start(),"end":m.end(),"label":"env","score":RULE_SCORE})
    for m in RE_SLA.finditer(text):    spans.append({"start":m.start(),"end":m.end(),"label":"sla","score":RULE_SCORE})
    return spans

def valid_model_span(s):
    sc = s.get("score", s.get("prob", s.get("confidence", None)))
    if sc is None: return False
    sc=float(sc)
    return sc >= MIN_SCORE.get(s["label"],0.0)

def merge_spans(spans):
    by=defaultdict(list)
    for s in spans:
        by[s["label"]].append(dict(s))
    out=[]
    for lbl, arr in by.items():
        arr=sorted(arr,key=lambda x:x.get("score",0.0),reverse=True)
        kept=[]
        for s in arr:
            keep=True
            for k in kept:
                if iou((s["start"],s["end"]),(k["start"],k["end"]))>=0.90:
                    k["start"]=min(k["start"],s["start"])
                    k["end"]=max(k["end"],s["end"])
                    k["score"]=max(k.get("score",0.0),s.get("score",0.0))
                    keep=False
                    break
            if keep: kept.append(s)
        out.extend(kept)
    return out

# ---------- 3) 產生混合式預測 ----------
# 先把所有 pred 檔按 text-hash 建索引，避免重複掃多次
pred_index = defaultdict(list)  # key -> spans[]
for pf in pred_files:
    for r in load_jsonl(pf):
        t = r.get("text") or r.get("body") or r.get("subject") or ""
        if not t: continue
        k = text_hash(t)
        cur=[]
        for s in (r.get("spans") or []):
            lb = norm_label(s.get("label",""))
            if lb not in ALLOW_LABELS: continue
            try:
                s0=int(s["start"]); e0=int(s["end"])
                if e0<=s0: continue
            except Exception:
                continue
            cand={"start":s0,"end":e0,"label":lb}
            sc = s.get("score", s.get("prob", s.get("confidence", None)))
            if sc is None: 
                # 缺分數的模型 span 一律丟棄（修掉 FP 爆炸）
                continue
            cand["score"]=float(sc)
            if not valid_model_span(cand): 
                continue
            cur.append(cand)
        if cur:
            pred_index[k].extend(cur)

hybrid=[]
total_kept=0
for r in load_jsonl(gold_p):
    t=r["text"]; k=text_hash(t)
    spans = []
    # 模型（已過濾低分與缺分數）
    if pred_index.get(k):
        spans.extend(pred_index[k])
    # 規則補召回
    spans.extend(rule_spans(t))
    # 合併/NMS
    spans = merge_spans(spans)
    total_kept += len(spans)
    hybrid.append({"text":t,"spans":spans})

hyb_p = OUTDIR/"hybrid_preds.jsonl"
dump_jsonl(hybrid, hyb_p)
print(f"[OK] hybrid preds -> {hyb_p} total_kept_spans={total_kept}")

# ---------- 4) 評測（strict / lenient） ----------
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
        if not matched:
            cnt[gl]["FN"]+=1
    for pi,p in enumerate(pred_spans):
        if pi not in used:
            cnt[p["label"]]["FP"]+=1
    return cnt

def metrics(cnt):
    labels=sorted(cnt.keys())
    rows=[]; microTP=microFP=microFN=0
    for lb in labels:
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

strict_cnt = {"amount":{"TP":0,"FP":0,"FN":0},"date_time":{"TP":0,"FP":0,"FN":0},"env":{"TP":0,"FP":0,"FN":0},"sla":{"TP":0,"FP":0,"FN":0}}
len_cnt    = {"amount":{"TP":0,"FP":0,"FN":0},"date_time":{"TP":0,"FP":0,"FN":0},"env":{"TP":0,"FP":0,"FN":0},"sla":{"TP":0,"FP":0,"FN":0}}

hy_by_k = { text_hash(r["text"]): r for r in hybrid }
for g in load_jsonl(gold_p):
    k=text_hash(g["text"])
    p = hy_by_k.get(k, {"spans":[]})
    gsp=[{"label":norm_label(s["label"]), "start":int(s["start"]), "end":int(s["end"])}
         for s in (g.get("spans") or []) if norm_label(s.get("label","")) in ALLOW_LABELS]
    psp=[{"label":norm_label(s["label"]), "start":int(s["start"]), "end":int(s["end"])}
         for s in (p.get("spans") or []) if norm_label(s.get("label","")) in ALLOW_LABELS]
    sc = prf_counts(gsp, psp, lenient=False)
    lc = prf_counts(gsp, psp, lenient=True)
    for lb in strict_cnt:
        for k2 in ("TP","FP","FN"):
            strict_cnt[lb][k2]+=sc[lb][k2]
            len_cnt[lb][k2]+=lc[lb][k2]

mS = metrics(strict_cnt)
mL = metrics(len_cnt)

md=[]
md.append("# KIE span metrics (hybrid hotfix)")
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

md_p = OUTDIR/"metrics_kie_spans.md"
(Path(md_p)).write_text("\n".join(md),encoding="utf-8")
print(f"[OK] wrote {md_p}")

# ---------- 5) 附到最新 ONECLICK 狀態檔 ----------
st_dir = ROOT/"reports_auto/status"
if st_dir.exists():
    latest = sorted(st_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
    if latest:
        with latest[0].open("a",encoding="utf-8") as f:
            f.write("\n## KIE span metrics (hybrid hotfix)\n")
            f.write(Path(md_p).read_text("utf-8"))
        print(f"[OK] appended metrics to {latest[0].as_posix()}")
PY

LATEST="$(ls -td reports_auto/kie_eval/* | head -n1)"
echo ">>> Result => $LATEST/metrics_kie_spans.md"
sed -n '1,200p' "$LATEST/metrics_kie_spans.md" || true
