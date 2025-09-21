#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT" || { echo "[FATAL] $ROOT"; exit 2; }
[[ -d .venv ]] || python3 -m venv .venv; . .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}" TOKENIZERS_PARALLELISM=false
mkdir -p .sma_tools scripts reports_auto/{logs,diagnostics}
TS="$(date +%Y%m%dT%H%M%S)"; LOG="reports_auto/logs/repair_pack_${TS}.log"
exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1
trap 'ec=$?; echo "[ERROR] exit=$ec cmd:${BASH_COMMAND}"; tail -n 200 "$LOG" > "reports_auto/diagnostics/REPAIR_TAIL_${TS}.log"; exit $ec' ERR

install_file() { # install_file <target> <marker> <<'EOF' ... EOF
  local tgt="$1"; local marker="$2"; shift 2
  local tmp; tmp="$(mktemp)"; cat > "$tmp"
  if [[ -s "$tgt" ]]; then
    # 只在缺 marker、含 \p{、或內容不同時覆蓋
    if grep -q "$marker" "$tgt" && ! grep -q "\\\\p{" "$tgt"; then
      if cmp -s "$tgt" "$tmp"; then
        echo "[SKIP] $tgt (same & clean)"; rm -f "$tmp"; return
      fi
    fi
  fi
  mkdir -p "$(dirname "$tgt")"; mv -f "$tmp" "$tgt"; echo "[WRITE] $tgt"
}

# ---- .sma_tools/gold_fix_ids.py ----
install_file ".sma_tools/gold_fix_ids.py" "# GOLD_FIX_IDS v1" <<'PY'
#!/usr/bin/env python3
# GOLD_FIX_IDS v1
import argparse, json, re, hashlib, unicodedata
from pathlib import Path

def norm(s):
    if s is None: return ""
    s = unicodedata.normalize("NFKC", str(s)).replace("\u3000"," ").lower()
    return re.sub(r"\s+"," ",s).strip()

def extract_text(o):
    parts=[]
    for k in ("subject","title","content","body","text","subject_norm","body_norm","text_norm","plain","raw_text"):
        v=o.get(k)
        if isinstance(v,str): parts.append(v)
    for kk in ("src","source","email","payload","data"):
        v=o.get(kk)
        if isinstance(v,dict):
            for k in ("subject","title","content","body","text","plain","raw_text","snippet","summary","description","text_norm","body_norm"):
                vv=v.get(k)
                if isinstance(vv,str): parts.append(vv)
    return norm("\n".join(parts))

def find_id(o):
    for k in ("id","corr_id","gold_id","message_id","uid"):
        v=o.get(k)
        if isinstance(v,(str,int)) and str(v).strip(): return str(v)
    blob=json.dumps(o,ensure_ascii=False)
    m=re.search(r"\bi-\d{8}-\d{3,6}\b", blob)
    if m: return m.group(0)
    txt=extract_text(o)
    if not txt: return None
    return "g-" + hashlib.sha1(txt.encode("utf-8","ignore")).hexdigest()[:16]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    a=ap.parse_args()
    n=0; fixed=0
    with open(a.inp,encoding="utf-8",errors="ignore") as f, open(a.out,"w",encoding="utf-8") as g:
        for ln in f:
            if not ln.strip(): continue
            o=json.loads(ln); n+=1
            if not o.get("id"):
                fid=find_id(o)
                if fid: o["id"]=fid; fixed+=1
            g.write(json.dumps(o,ensure_ascii=False)+"\n")
    print(f"[GOLD_FIX] total={n} fixed={fixed} OUT={a.out}")

if __name__=="__main__": main()
PY
chmod +x .sma_tools/gold_fix_ids.py

# ---- .sma_tools/align_gold_to_pred.py ----
install_file ".sma_tools/align_gold_to_pred.py" "# ALIGN_G2P v2" <<'PY'
#!/usr/bin/env python3
# ALIGN_G2P v2
import argparse, json, csv, os, re, hashlib, unicodedata
from collections import defaultdict, deque

WANTED_KEYS={"subject","subject_norm","title","body","body_norm","content","text","text_norm","plain","raw_text","message","snippet","summary","desc","description"}
ID_KEYS=("id","corr_id","gold_id","pred_id","message_id","uid")

def norm_text(s:str)->str:
    if s is None: return ""
    s=unicodedata.normalize("NFKC",str(s)).replace("\u3000"," ").lower()
    return re.sub(r"\s+"," ",s).strip()

def iter_strings(o,max_items=64):
    out=[];q=deque([o]);n=0
    while q and n<10000:
        n+=1;cur=q.popleft()
        if isinstance(cur,dict):
            for k,v in cur.items():
                if isinstance(v,str) and (k in WANTED_KEYS or k.lower() in WANTED_KEYS): out.append(v)
                elif isinstance(v,(dict,list)): q.append(v)
        elif isinstance(cur,list):
            for v in cur:
                if isinstance(v,(dict,list)): q.append(v)
    return out[:max_items]

def extract_text(o:dict)->str:
    parts=[]
    for k in ("subject","title","content","body","text","subject_norm","body_norm","text_norm","plain","raw_text"):
        v=o.get(k); 
        if isinstance(v,str): parts.append(v)
    for kk in ("src","source","email","payload","data","intent","spam","kie"):
        v=o.get(kk)
        if isinstance(v,dict):
            for k2 in ("subject","subject_norm","title","body","body_norm","content","text","text_norm","plain","raw_text","message","snippet","summary","desc","description"):
                vv=v.get(k2)
                if isinstance(vv,str): parts.append(vv)
    if len(parts)<4: parts.extend(iter_strings(o))
    return norm_text("\n".join(parts))

def fingerprint(txt:str)->str:
    txt=re.sub(r"[\x00-\x1F\x7F]+"," ",txt)
    try:
        import regex as _re
        txt=_re.sub(r"\p{P}+","",txt); txt=_re.sub(r"\p{Z}+"," ",txt)
    except Exception:
        txt=re.sub(r"[^\w\u4e00-\u9fff]+"," ",txt)
    return hashlib.sha1(norm_text(txt).encode("utf-8","ignore")).hexdigest()

def ngrams(s,n=3): return {s[i:i+n] for i in range(max(0,len(s)-n+1))} if s else set()
def jaccard(a,b):
    if not a or not b: return 0.0
    A,B=ngrams(a),ngrams(b); u=len(A|B)
    return (len(A&B)/u) if u else 0.0

def load_jsonl(p):
    with open(p,encoding="utf-8",errors="ignore") as f:
        for ln in f:
            if ln.strip(): yield json.loads(ln)

def find_id_like(o):
    for k in ID_KEYS:
        v=o.get(k)
        if isinstance(v,(str,int)) and str(v).strip(): return str(v)
    for s in iter_strings(o,128):
        m=re.search(r"\bi-\d{8}-\d{3,6}\b",s)
        if m: return m.group(0)
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold",required=True); ap.add_argument("--pred",required=True)
    ap.add_argument("--out",default="reports_auto/alignment/gold2pred.csv")
    ap.add_argument("--mode",choices=["auto","exact","fuzzy"],default="auto")
    ap.add_argument("--fuzzy_threshold",type=float,default=0.90)
    a=ap.parse_args()

    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    os.makedirs("reports_auto/alignment",exist_ok=True)

    gold=list(load_jsonl(a.gold)); pred=list(load_jsonl(a.pred))

    # 補 gold 缺 id
    fixed=0
    for o in gold:
        if not o.get("id"):
            fid=find_id_like(o)
            if fid: o["id"]=fid; fixed+=1

    pred_by_id={o["id"]:o for o in pred if isinstance(o.get("id"),(str,int))}
    gold_by_id={o["id"]:o for o in gold if isinstance(o.get("id"),(str,int))}

    mapping={}; used=set()
    for gid in list(gold_by_id):
        if gid in pred_by_id: mapping[gid]=(gid,"id",1.0); used.add(gid)

    pred_fp_idx=defaultdict(list); pred_txt={}
    for o in pred:
        pid=o.get("id"); 
        if not isinstance(pid,(str,int)): continue
        txt=extract_text(o); pred_txt[pid]=txt
        pred_fp_idx[fingerprint(txt)].append(pid)

    need=[o for o in gold if o.get("id") not in mapping]
    if a.mode in ("auto","exact"):
        still=[]
        for o in need:
            gid=o.get("id"); txt=extract_text(o); fp=fingerprint(txt)
            cand=[pid for pid in pred_fp_idx.get(fp,[]) if pid not in used]
            if len(cand)==1: mapping[gid]=(cand[0],"fingerprint",1.0); used.add(cand[0])
            else: still.append(o)
        need=still

    if a.mode in ("auto","fuzzy") and need:
        for o in need:
            gid=o.get("id"); gtxt=extract_text(o)
            best_pid,best_sim=None,-1.0
            for pid,ptxt in pred_txt.items():
                if pid in used: continue
                sim=jaccard(gtxt,ptxt)
                if sim>best_sim: best_pid,best_sim=pid,sim
            if best_pid is not None and best_sim>=a.fuzzy_threshold:
                mapping[gid]=(best_pid,"fuzzy",best_sim); used.add(best_pid)

    matched=len(mapping); total=len(gold)
    ambig=sum(1 for _,ids in pred_fp_idx.items() if len(ids)>1)
    with open(a.out,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["gold_id","pred_id","method","similarity"])
        for gid,(pid,m,sc) in mapping.items(): w.writerow([gid,pid,m,f"{sc:.4f}"])
    summ=(f"TOTAL_GOLD={total}\nMATCHED={matched}\nCOVERAGE={matched/total if total else 0:.4f}\n"
          f"PRED_FINGERPRINT_AMBIG={ambig}\nGOLD_ID_FILLED={fixed}\nOUT={a.out}\n")
    print(summ)
    with open("reports_auto/alignment/ALIGN_SUMMARY.txt","w",encoding="utf-8") as f: f.write(summ)

if __name__=="__main__": main()
PY
chmod +x .sma_tools/align_gold_to_pred.py

# ---- .sma_tools/eval_intent_spam.py ----
install_file ".sma_tools/eval_intent_spam.py" "# EVAL_INTENT_SPAM v1" <<'PY'
#!/usr/bin/env python3
# EVAL_INTENT_SPAM v1
import argparse, json, csv, os, collections
def load_jsonl(p):
    with open(p,encoding="utf-8",errors="ignore") as f:
        for ln in f:
            if ln.strip(): yield json.loads(ln)
def load_gold(p):
    m={}
    for o in load_jsonl(p):
        gid=o.get("id"); lab=o.get("label")
        if gid is not None: m[gid]=lab
    return m
def load_pred_maps(p):
    P_int={}; P_sp_lab={}; P_sp_scr={}
    for o in load_jsonl(p):
        pid=o.get("id"); 
        if not pid: continue
        it=o.get("intent") or {}; sp=o.get("spam") or {}
        tuned=it.get("tuned")
        if tuned is not None: P_int[pid]=tuned
        score=float(sp.get("score_text",0.0)); P_sp_scr[pid]=score
        P_sp_lab[pid]=1 if score>=0.5 else 0
        if "label" in sp:
            try: P_sp_lab[pid]=int(sp["label"])
            except Exception: pass
    return P_int,P_sp_lab,P_sp_scr
def load_map_csv(p):
    m={}
    with open(p,encoding="utf-8",newline="") as f:
        for i,row in enumerate(csv.reader(f)):
            if i==0 and row and row[0]=="gold_id": continue
            if not row: continue
            gid=row[0]; pid=row[1] if len(row)>1 else None
            if gid and pid: m[gid]=pid
    return m
def acc(y,yh): return sum(a==b for a,b in zip(y,yh))/len(y) if y else 0.0
def prf(y,yh,labels):
    TP=collections.Counter(); FP=collections.Counter(); FN=collections.Counter()
    for t,p in zip(y,yh):
        if p==t: TP[t]+=1
        else: FP[p]+=1; FN[t]+=1
    z=lambda a,b: (a/b) if b else 0.0
    prec={l:z(TP[l],TP[l]+FP[l]) for l in labels}
    rec ={l:z(TP[l],TP[l]+FN[l]) for l in labels}
    f1  ={l:(z(2*prec[l]*rec[l],prec[l]+rec[l]) if (prec[l]+rec[l]) else 0.0) for l in labels}
    sup=collections.Counter(y)
    macro=sum(f1.values())/len(labels) if labels else 0.0
    micro_tp=sum(TP.values()); micro_fp=sum(FP.values()); micro_fn=sum(FN.values())
    micro_p=z(micro_tp,micro_tp+micro_fp); micro_r=z(micro_tp,micro_tp+micro_fn)
    micro=z(2*micro_p*micro_r,micro_p+micro_r) if (micro_p+micro_r) else 0.0
    w=z(sum(f1[l]*sup[l] for l in labels), len(y))
    return prec,rec,f1,macro,micro,w,sup,TP,FP,FN
def auc(y_true,y_score):
    P=sum(1 for y in y_true if y==1); N=len(y_true)-P
    if P==0 or N==0: return None
    wins=ties=0
    pos=[s for s,y in zip(y_score,y_true) if y==1]
    neg=[s for s,y in zip(y_score,y_true) if y==0]
    for sp in pos:
        for sn in neg:
            if sp>sn: wins+=1
            elif sp==sn: ties+=1
    return (wins+0.5*ties)/(P*N)
def conf(y,yh,labels):
    idx={l:i for i,l in enumerate(labels)}
    m=[[0]*len(labels) for _ in labels]
    for t,p in zip(y,yh): m[idx[t]][idx[p]]+=1
    return m
def write_cm(p,labels,mat):
    with open(p,"w",encoding="utf-8") as f:
        f.write("label,"+",".join(map(str,labels))+"\n")
        for i,l in enumerate(labels): f.write(str(l)+","+",".join(map(str,mat[i]))+"\n")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--task",choices=["intent","spam"],required=True)
    ap.add_argument("--gold",required=True); ap.add_argument("--pred",required=True)
    ap.add_argument("--map",required=True);  ap.add_argument("--out",required=True)
    ap.add_argument("--spam_threshold",type=float,default=0.5)
    a=ap.parse_args()
    os.makedirs(os.path.dirname(a.out),exist_ok=True)
    G=load_gold(a.gold); P_int,P_sp_lab,P_sp_scr=load_pred_maps(a.pred); M=load_map_csv(a.map)
    y=[]; yh=[]; ids=[]
    if a.task=="intent":
        for gid,gl in G.items():
            pid=M.get(gid); 
            if not pid or pid not in P_int: continue
            y.append(gl); yh.append(P_int[pid]); ids.append((gid,pid))
        labels=sorted(set(y)|set(yh)); A=acc(y,yh)
        prec,rec,f1,ma,mi,w,sup,TP,FP,FN=prf(y,yh,labels); CM=conf(y,yh,labels)
        with open(a.out,"w",encoding="utf-8") as f:
            f.write(f"TASK=intent\nGOLD={len(G)} MATCHED={len(ids)} COVERAGE={len(ids)/len(G) if G else 0:.4f}\n")
            f.write(f"ACCURACY={A:.4f}\nF1_macro={ma:.4f} F1_micro={mi:.4f} F1_weighted={w:.4f}\n")
            f.write("PER_LABEL (label, support, precision, recall, f1)\n")
            for l in labels: f.write(f"{l}\t{sup[l]}\t{prec[l]:.4f}\t{rec[l]:.4f}\t{f1[l]:.4f}\n")
        write_cm(a.out.replace(".txt","_confusion.csv"),labels,CM)
        with open(a.out.replace(".txt","_miscls.csv"),"w",encoding="utf-8",newline="") as f:
            wcsv=csv.writer(f); wcsv.writerow(["gold_id","pred_id","gold","pred"])
            for (gid,pid),gt,pt in zip(ids,y,yh):
                if gt!=pt: wcsv.writerow([gid,pid,gt,pt])
    else:
        th=float(a.spam_threshold)
        for gid,gl in G.items():
            pid=M.get(gid); 
            if not pid or pid not in P_sp_lab: continue
            y.append(int(gl)); yh.append(1 if P_sp_scr.get(pid,0.0)>=th else 0); ids.append((gid,pid))
        labels=[0,1]; A=acc(y,yh)
        prec,rec,f1,ma,mi,w,sup,TP,FP,FN=prf(y,yh,labels); CM=conf(y,yh,labels)
        ROC=auc(y,[P_sp_scr.get(pid,0.0) for _,pid in ids])
        with open(a.out,"w",encoding="utf-8") as f:
            f.write(f"TASK=spam threshold={th}\nGOLD={len(G)} MATCHED={len(ids)} COVERAGE={len(ids)/len(G) if G else 0:.4f}\n")
            f.write(f"ACCURACY={A:.4f} AUC={(ROC if ROC is not None else 'NA')}\n")
            f.write(f"F1_macro={ma:.4f} F1_micro={mi:.4f} F1_weighted={w:.4f}\n")
            f.write("PER_LABEL (label, support, precision, recall, f1, TP, FP, FN)\n")
            for l in labels: f.write(f"{l}\t{sup[l]}\t{prec[l]:.4f}\t{rec[l]:.4f}\t{f1[l]:{'.4f'}}\t{TP[l]}\t{FP[l]}\t{FN[l]}\n")
        write_cm(a.out.replace(".txt","_confusion.csv"),labels,CM)
        with open(a.out.replace(".txt","_miscls.csv"),"w",encoding="utf-8",newline="") as f:
            wcsv=csv.writer(f); wcsv.writerow(["gold_id","pred_id","gold","pred"])
            for (gid,pid),gt,pt in zip(ids,y,yh):
                if gt!=pt: wcsv.writerow([gid,pid,gt,pt])
    print(f"[WRITE] {a.out}")
if __name__=="__main__": main()
PY
chmod +x .sma_tools/eval_intent_spam.py

# ---- scripts/oneclick_all_in_one.sh ----
install_file "scripts/oneclick_all_in_one.sh" "# ONECLICK_ALL v3" <<'BASH2'
#!/usr/bin/env bash
# ONECLICK_ALL v3
set -Eeuo pipefail
INFER_IN="${INFER_IN:-data/intent/external_realistic_test.clean.jsonl}"
MIN_PROB="${MIN_PROB:-0.25}"; FUZZY_TH="${FUZZY_TH:-0.90}"; SPAM_TH="${SPAM_TH:-0.50}"
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT" || { echo "[FATAL] $ROOT"; exit 2; }
[[ -d .venv ]] || python3 -m venv .venv; . .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}" TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p reports_auto/{logs,status,alignment,silver,diagnostics} .sma_tools
TS="$(date +%Y%m%dT%H%M%S)"; LOG="reports_auto/logs/oneclick_all_${TS}.log"; ln -sf "$(basename "$LOG")" reports_auto/logs/latest.log || true
exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1; PS4='+ [\t] ' ; set -x
trap 'ec=$?; echo; echo "[ERROR] exit=$ec line:$LINENO cmd:${BASH_COMMAND}"; tail -n 200 "$LOG" > "reports_auto/diagnostics/LAST_TAIL_${TS}.log" || true; printf "exit=%s\ncmd=%s\n" "$ec" "${BASH_COMMAND}" > "reports_auto/diagnostics/LAST_CAUSE_${TS}.txt"; exit $ec' ERR

shopt -s nullglob
for p in "$INFER_IN" reports_auto/predict_all.jsonl data/intent/*.jsonl data/spam/*.jsonl; do [[ -f "$p" ]] && sed -i 's/\r$//' "$p"; done
shopt -u nullglob

[[ -f "$INFER_IN" ]] || { echo "[FATAL] 缺少輸入：$INFER_IN"; exit 3; }
python .sma_tools/jsonl_doctor.py normalize -i "$INFER_IN" -o "$INFER_IN.tmp" && mv -f "$INFER_IN.tmp" "$INFER_IN"
python .sma_tools/sma_infer_all_three.py --in "$INFER_IN" --out reports_auto/predict_all.jsonl
python .sma_tools/jsonl_doctor.py normalize -i reports_auto/predict_all.jsonl -o reports_auto/predict_all.jsonl.tmp && mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl

cp -f reports_auto/predict_all.jsonl reports_auto/predict_all.jsonl.kie_in
PYTHONPATH="src:.sma_tools" python .sma_tools/sma_kie_add.py \
  --src "$INFER_IN" --pred_in reports_auto/predict_all.jsonl.kie_in \
  --pred_out reports_auto/predict_all.jsonl --kie_dir artifacts_kie/model \
  --chunk 4 --maxlen 512 --min_prob "$MIN_PROB" --keep_labels amount,env,sla,date_time
python .sma_tools/jsonl_doctor.py normalize -i reports_auto/predict_all.jsonl -o reports_auto/predict_all.jsonl.tmp && mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl
python .sma_tools/kie_regex_fill.py --in reports_auto/predict_all.jsonl --out reports_auto/predict_all.jsonl.tmp --only-empty 1 && mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl
python - <<'PY'
import json,os
p="reports_auto/predict_all.jsonl"; q=p+".tmp"
with open(p,encoding="utf-8") as f, open(q,"w",encoding="utf-8") as g:
    for ln in f:
        if not ln.strip(): g.write(ln); continue
        o=json.loads(ln); spans=((o.get("kie") or {}).get("spans") or [])
        for s in spans: s.setdefault("source","kie")
        g.write(json.dumps(o,ensure_ascii=False)+"\n")
os.replace(q,p)
PY

python - <<'PY'
import json, os
os.makedirs("reports_auto/silver", exist_ok=True)
pred="reports_auto/predict_all.jsonl"
fi=open("reports_auto/silver/intent_silver.jsonl","w",encoding="utf-8")
fs=open("reports_auto/silver/spam_silver.jsonl","w",encoding="utf-8")
keep_i=keep_s=0; ids=set()
for ln in open(pred,encoding="utf-8"):
    if not ln.strip(): continue
    o=json.loads(ln); i=o.get("id")
    if not i: continue
    ids.add(i)
    it=o.get("intent") or {}; sp=o.get("spam") or {}
    p1=float(it.get("p1",0.0)); p2=float(it.get("p2",0.0)); tuned=it.get("tuned")
    if tuned and p1>=0.60 and (p1-p2)>=0.08:
        fi.write(json.dumps({"id":i,"label":tuned},ensure_ascii=False)+"\n"); keep_i+=1
    score=float(sp.get("score_text",0.0))
    fs.write(json.dumps({"id":i,"label":1 if score>=0.5 else 0},ensure_ascii=False)+"\n"); keep_s+=1
fi.close(); fs.close()
Pi={o["id"]:(o.get("intent") or {}).get("tuned") for o in map(json.loads, open(pred,encoding="utf-8")) if o.get("id")}
Ps={o["id"]:int((o.get("spam") or {}).get("score_text",0.0)>=0.5) for o in map(json.loads, open(pred,encoding="utf-8")) if o.get("id")}
def loadm(p): 
    m={}; 
    for ln in open(p,encoding="utf-8"):
        if ln.strip():
            o=json.loads(ln); m[o["id"]]=o["label"]
    return m
Gi=loadm("reports_auto/silver/intent_silver.jsonl"); Gs=loadm("reports_auto/silver/spam_silver.jsonl")
def acc(G,P):
    pair=[(G[k],P[k]) for k in G if k in P]; 
    return (sum(a==b for a,b in pair)/len(pair), len(pair)) if pair else (None,0)
ai,ni=acc(Gi,Pi); as_,ns=acc(Gs,Ps)
open("reports_auto/status/SILVER_SELF_CHECK.txt","w",encoding="utf-8").write(
    f"SILVER intent_kept={keep_i}, spam_kept={keep_s}, pred_ids={len(ids)}\n"
    f"SELF_CHECK intent_acc={ai} (n={ni}), spam_acc={as_} (n={ns})\n"
)
print(f"[SILVER] intent_kept={keep_i} spam_kept={keep_s} pred_ids={len(ids)}")
print(f"[SELF-CHECK] intent_acc={ai} (n={ni}) | spam_acc={as_} (n={ns})")
PY

python - <<'PY'
import json,collections,os
cnt=collections.Counter(); src=collections.Counter(); empt=0; n=0
for ln in open("reports_auto/predict_all.jsonl",encoding="utf-8"):
    if not ln.strip(): continue
    n+=1
    o=json.loads(ln); spans=(o.get("kie") or {}).get("spans") or []
    if not spans: empt+=1
    for s in spans: cnt[s.get("label","_")]+=1; src[s.get("source","kie")]+=1
open("reports_auto/status/KIE_SUMMARY.txt","w",encoding="utf-8").write(
    f"TOTAL={n} EMPTY={empt}\nLABEL={dict(cnt)}\nSOURCE={dict(src)}\n"
)
print(f"[SUMMARY] TOTAL={n} EMPTY={empt} | LABEL={dict(cnt)} | SOURCE={dict(src)}")
PY

GOLD_PATH=""
if [[ -f data/intent/test_labeled.fixed.jsonl ]]; then GOLD_PATH="data/intent/test_labeled.fixed.jsonl";
elif [[ -f data/intent/test_labeled.jsonl ]]; then GOLD_PATH="data/intent/test_labeled.jsonl"; fi

if [[ -n "$GOLD_PATH" ]]; then
  python .sma_tools/align_gold_to_pred.py --gold "$GOLD_PATH" --pred reports_auto/predict_all.jsonl \
    --out reports_auto/alignment/gold2pred_intent.csv --mode auto --fuzzy_threshold "$FUZZY_TH"
  python .sma_tools/eval_intent_spam.py --task intent --gold "$GOLD_PATH" --pred reports_auto/predict_all.jsonl \
    --map reports_auto/alignment/gold2pred_intent.csv --out reports_auto/metrics_intent.txt
fi

if [[ -f data/spam/test_labeled.jsonl ]]; then
  python .sma_tools/align_gold_to_pred.py --gold data/spam/test_labeled.jsonl --pred reports_auto/predict_all.jsonl \
    --out reports_auto/alignment/gold2pred_spam.csv --mode auto --fuzzy_threshold "$FUZZY_TH"
  python .sma_tools/eval_intent_spam.py --task spam --gold data/spam/test_labeled.jsonl --pred reports_auto/predict_all.jsonl \
    --map reports_auto/alignment/gold2pred_spam.csv --out reports_auto/metrics_spam.txt --spam_threshold "$SPAM_TH"
fi

python - <<'PY'
import pathlib,datetime
R=pathlib.Path("reports_auto/status"); R.mkdir(parents=True,exist_ok=True)
def readp(p): 
    try: return pathlib.Path(p).read_text(encoding="utf-8").strip()
    except: return ""
md=R/("ONECLICK_SUMMARY_"+datetime.datetime.now().strftime("%Y%m%dT%H%M%S")+".md")
body=[]
body.append("# ONECLICK Summary\n\n## Silver Self-Check\n```\n"+readp("reports_auto/status/SILVER_SELF_CHECK.txt")+"\n```\n")
body.append("## KIE Summary\n```\n"+readp("reports_auto/status/KIE_SUMMARY.txt")+"\n```\n")
for name in ("metrics_intent.txt","metrics_spam.txt"):
    p="reports_auto/"+name
    if pathlib.Path(p).exists(): body.append(f"## {name}\n```\n"+readp(p)+"\n```\n")
md.write_text("\n".join(body),encoding="utf-8")
print(f"[WRITE] {md}")
PY
echo "[DONE] oneclick_all_in_one completed (log: $LOG)"
BASH2
chmod +x scripts/oneclick_all_in_one.sh

echo "[OK] repair_pack done. Run next: python .sma_tools/gold_fix_ids.py --in data/intent/test_labeled.jsonl --out data/intent/test_labeled.fixed.jsonl"
