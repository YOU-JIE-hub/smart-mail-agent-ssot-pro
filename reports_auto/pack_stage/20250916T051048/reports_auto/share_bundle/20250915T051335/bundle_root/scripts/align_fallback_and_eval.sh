#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT" || exit 2
[[ -d .venv ]] || python3 -m venv .venv; . .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}" TOKENIZERS_PARALLELISM=false
mkdir -p reports_auto/{alignment,diagnostics,logs}

PRED="reports_auto/predict_all.jsonl"
GOLD_INT="data/intent/test_labeled.fixed.jsonl"
[[ -f "$GOLD_INT" ]] || GOLD_INT="data/intent/test_labeled.jsonl"

python - <<'PY'
import json,re,unicodedata,csv,email.utils,datetime as dt, pathlib
def load(p):
    out=[]; 
    with open(p,encoding="utf-8",errors="ignore") as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out
def norm(s):
    if s is None: return ""
    s=unicodedata.normalize("NFKC",str(s)).replace("\u3000"," ").lower()
    return re.sub(r"\s+"," ",s).strip()
def fdt(s):
    if s is None: return None
    try:
        if isinstance(s,(int,float)): return float(s)
        ss=str(s).strip()
        if re.fullmatch(r"\d{10}(\.\d+)?",ss): return float(ss)
        try: return email.utils.parsedate_to_datetime(ss).timestamp()
        except: return dt.datetime.fromisoformat(ss.replace("Z","+00:00")).timestamp()
    except: return None
def first(o,keys):
    for ks in keys:
        v=o
        if isinstance(ks,(list,tuple)):
            for k in ks:
                if not isinstance(v,dict): v=None; break
                v=v.get(k)
        else: v=o.get(ks)
        if isinstance(v,str) and v.strip(): return v
    return None
def ext(o):
    subj=(first(o,["subject"]) or first(o,[["src","subject"],["subject_norm"],["email","subject"],["payload","subject"]]) or "")
    fr  =(first(o,["from","sender","from_email"]) or first(o,[["src","from"],["email","from"],["headers","from"]]) or "")
    to  =(first(o,["to","to_email"]) or first(o,[["src","to"],["email","to"],["headers","to"]]) or "")
    date=(first(o,["date","timestamp","ts","time","sent_at"]) or first(o,[["src","date"],["email","date"],["headers","date"]]))
    ts  =fdt(date)
    parts=[]
    for k in ("content","text","body","snippet","summary","description","plain","raw_text","text_norm","body_norm"):
        v=o.get(k); 
        if isinstance(v,str): parts.append(v)
    for kk in ("src","source","email","payload","data"):
        v=o.get(kk)
        if isinstance(v,dict):
            for k in ("content","text","body","snippet","summary","description","plain","raw_text","text_norm","body_norm"):
                vv=v.get(k)
                if isinstance(vv,str): parts.append(vv)
    return norm(subj),norm(fr),norm(to),ts,norm("\n".join(parts))[:2000]
def ngr(s,n=3): return {s[i:i+n] for i in range(max(0,len(s)-n+1))} if s else set()
def jac(a,b):
    if not a or not b: return 0.0
    A,B=ngr(a),ngr(b); u=len(A|B); return (len(A&B)/u) if u else 0.0

pred=load("reports_auto/predict_all.jsonl")
gold=load(__import__('os').environ.get("GOLD_INT"))

# 填補 gold.id
import re, json
def fill_id(o):
    for k in ("id","corr_id","message_id","uid","gold_id"):
        v=o.get(k)
        if isinstance(v,(str,int)) and str(v).strip(): o.setdefault("id",str(v)); return True
    blob=json.dumps(o,ensure_ascii=False)
    m=re.search(r"\bi-\d{8}-\d{3,6}\b",blob)
    if m: o.setdefault("id",m.group(0)); return True
    return False
filled=sum(fill_id(o) for o in gold)

P=[(o.get("id"),)+ext(o) for o in pred if o.get("id") is not None]
G=[(o.get("id"),o.get("label"),)+ext(o) for o in gold if o.get("id") is not None]
P_by_id={pid:i for i,(pid,*_) in enumerate(P)}
mapping={}; used=set()
for gid,_,*__ in G:
    if gid in P_by_id: mapping[gid]=(gid,"id",1.0); used.add(gid)

def sim(g,p):
    _,_,gsub,gs,gt,gtm,gcorp=g; _,psub,ps,pt,ptm,pcorp=p
    s_sub=jac(gsub,psub); s_body=jac(gcorp,pcorp)
    s_from=1.0 if gs and ps and gs==ps else 0.0
    s_to  =1.0 if gt and pt and gt==pt else 0.0
    bonus=0.05 if (gtm and ptm and abs(gtm-ptm)<=3*24*3600) else 0.0
    return 0.5*s_sub+0.4*s_body+0.05*s_from+0.05*s_to+bonus

TH=0.78
G_need=[g for g in G if g[0] not in mapping]
for g in G_need:
    best=(None,-1.0)
    for p in P:
        if p[0] in used: continue
        sc=sim(g,p)
        if sc>best[1]: best=(p[0],sc)
    if best[0] and best[1]>=TH:
        mapping[g[0]]=(best[0],"fallback",best[1]); used.add(best[0])

G_rem=[g for g in G_need if g[0] not in mapping]; P_rem=[p for p in P if p[0] not in used]
G_rem.sort(key=lambda x:x[2] or ""); P_rem.sort(key=lambda x:x[1] or "")
for g,p in zip(G_rem,P_rem): mapping[g[0]]=(p[0],"order",0.0)

out="reports_auto/alignment/gold2pred_intent_fallback.csv"
with open(out,"w",encoding="utf-8",newline="") as f:
    w=csv.writer(f); w.writerow(["gold_id","pred_id","method","similarity"])
    for gid,(pid,m,sc) in mapping.items(): w.writerow([gid,pid,m,f"{sc:.4f}"])
print(f"[FALLBACK] GOLD={len(G)} MATCHED={len(mapping)} TH={TH} GOLD_ID_FILLED={filled}")
PY

# 正式輸出 fallback metrics（intent，用什麼 gold 取決於上面的 GOLD_INT）
python .sma_tools/eval_intent_spam.py --task intent \
  --gold "$GOLD_INT" --pred reports_auto/predict_all.jsonl \
  --map  reports_auto/alignment/gold2pred_intent_fallback.csv \
  --out  reports_auto/metrics_intent_fallback.txt

# 同步到主名，讓其他腳本直接讀
cp -f reports_auto/alignment/gold2pred_intent_fallback.csv reports_auto/alignment/gold2pred_intent.csv
cp -f reports_auto/metrics_intent_fallback.txt       reports_auto/metrics_intent.txt

echo "[DONE] align_fallback_and_eval"
