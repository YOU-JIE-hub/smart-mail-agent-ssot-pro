#!/usr/bin/env bash
# v11: 解壓 artifacts_inbox/*.zip → 入倉 spam/intent → KIE 權重擇優
# → 組 Spam/Intent 評測集（多來源遞迴掃描、去重、壞行容錯）
# → 跑 evaluator（若有）→ 自算 Intent(門檻+規則) → 掛 KIE 附件 → 摘要
set -o pipefail
OLD="$HOME/projects/smart-mail-agent"
NEW="$HOME/projects/smart-mail-agent_ssot"
INBOX="$NEW/artifacts_inbox"
STAGED="$NEW/data/staged_project"
TS="$(date +%Y%m%dT%H%M%S)"
STATUS_DIR="$NEW/reports_auto/status"
ERR_DIR="$NEW/reports_auto/errors"
EVAL_DIR="$NEW/reports_auto/eval"
KIE_EVAL_DIR="$NEW/reports_auto/kie_eval"
LOG="$ERR_DIR/ONECLICK_v11_${TS}.log"
SUMMARY="$STATUS_DIR/ONECLICK_v11_${TS}.md"

mkdir -p "$STATUS_DIR" "$ERR_DIR" "$KIE_EVAL_DIR" \
         "$NEW/artifacts_prod" "$NEW/artifacts" "$NEW/kie/kie" \
         "$NEW/data/spam_eval" "$NEW/data/intent_eval" \
         "$NEW/src/smart_mail_agent/ml" "$NEW/configs" "$STAGED"

log(){ printf '%s\n' "$*" | tee -a "$LOG" >&2; }

cd "$NEW" 2>/dev/null || { echo "[FATAL] NEW 專案不存在：$NEW"; exit 2; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:src:scripts:.sma_tools:${PYTHONPATH:-}"

log "[STEP0] 解壓 artifacts_inbox/*.zip → $STAGED（若有）"
python - <<'PY'
from pathlib import Path
import zipfile, shutil, time
inbox=Path("artifacts_inbox"); staged=Path("data/staged_project")
staged.mkdir(parents=True, exist_ok=True)
cnt=0
for z in sorted(inbox.glob("*.zip")):
    out=staged/f"unzipped_{z.stem}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(z,"r") as zz: zz.extractall(out); cnt+=1
        print("[OK] unzip ->", out)
    except Exception as e:
        print("[WARN] unzip fail", z, "->", e)
print("[ZIP] processed:", cnt)
PY

log "[STEP1] 建 shim（legacy intent pickles 需要 rules_feat）"
cat > src/smart_mail_agent/ml/rules_feat.py <<'PY'
import numpy as np
class rules_feat:
    def __init__(self,*a,**k): self.n_features_=k.get("n_features_",1)
    def fit(self,X,y=None): return self
    def transform(self,X):
        n=len(X) if hasattr(X,"__len__") else 1
        d=int(self.n_features_) if isinstance(self.n_features_,int) else 1
        try: return np.zeros((n,d))
        except: return np.zeros((n,1))
PY

log "[STEP2] 入倉 spam/intent（優先 artifacts_inbox，其次 OLD）"
stage(){ [ -f "$1" ] && { cp -f "$1" "$2"; log "  staged $(basename "$1") -> $2"; }; }

# spam
stage "$INBOX/model_pipeline.pkl"   "artifacts_prod/model_pipeline.pkl"
stage "$INBOX/ens_thresholds.json"  "artifacts_prod/ens_thresholds.json"
stage "$INBOX/model_meta.json"      "artifacts_prod/model_meta.json"
stage "$INBOX/spam_rules.json"      "artifacts_prod/spam_rules.json"
[ -f artifacts_prod/model_pipeline.pkl ] || stage "$OLD/reports_auto/bundle_tmp/model_pipeline.pkl" "artifacts_prod/model_pipeline.pkl"
[ -f artifacts_prod/ens_thresholds.json ] || stage "$OLD/reports_auto/bundle_tmp/ens_thresholds.json" "artifacts_prod/ens_thresholds.json"
[ -f artifacts_prod/model_meta.json ] || stage "$OLD/reports_auto/spam/artifacts_prod/model_meta.json" "artifacts_prod/model_meta.json"
[ -f artifacts_prod/spam_rules.json ] || stage "$OLD/artifacts/spam/spam_rules.json" "artifacts_prod/spam_rules.json"

# intent
stage "$INBOX/intent_pro_cal.pkl"        "artifacts/intent_pro_cal.pkl"
stage "$INBOX/intent_pipeline_fixed.pkl" "artifacts/intent_pipeline_fixed.pkl"
stage "$INBOX/intent_clf.pkl"            "artifacts/intent_clf.pkl"
[ -f artifacts/intent_pro_cal.pkl ] || stage "$OLD"/artifacts/releases/intent/*/intent_pro_cal.pkl "artifacts/intent_pro_cal.pkl"
stage "$INBOX/intent_rules.json"         "configs/intent_rules.json" || true

log "[STEP3] 標準化門檻 + 編譯 intent 規則"
python - <<'PY'
import json, pathlib, re
root=pathlib.Path(".")
p=root/"artifacts_prod/ens_thresholds.json"
if p.exists():
    try:
        j=json.loads(p.read_text("utf-8")); thr=j.get("spam") if isinstance(j.get("spam"),(int,float)) else (j.get("threshold") or 0.44)
        p.write_text(json.dumps({"spam":float(thr)},ensure_ascii=False,indent=2),"utf-8"); print("[OK] spam thresholds ->", float(thr))
    except Exception as e:
        print("[WARN] ens_thresholds.json 解析失敗，用 0.44：", e); p.write_text(json.dumps({"spam":0.44},ensure_ascii=False,indent=2),"utf-8")
else:
    p.write_text(json.dumps({"spam":0.44},ensure_ascii=False,indent=2),"utf-8"); print("[OK] spam thresholds -> default 0.44")

it=root/"reports_auto/intent_thresholds.json"
if not it.exists():
    it.write_text(json.dumps({"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3},ensure_ascii=False,indent=2),"utf-8")
    print("[OK] intent thresholds -> default")

ir = root/"configs/intent_rules.json"
if ir.exists():
    try:
        j=json.loads(ir.read_text("utf-8"))
        rx={}
        for k,v in j.items():
            if isinstance(v,str): rx[k]=v
            elif isinstance(v,(list,tuple)): rx[k]="("+"|".join(map(re.escape,v))+")"
        out={"priority":["投訴","報價","技術支援","規則詢問","資料異動","其他"],"patterns":rx}
        (root/"configs/intent_rules_compiled.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
        print("[OK] compiled intent rules -> configs/intent_rules_compiled.json")
    except Exception as e:
        print("[WARN] intent_rules.json parse fail:", e)
else:
    print("[INFO] no intent_rules.json; will use built-ins if needed")
PY

log "[STEP4] 挑 KIE 權重（優先 artifacts_inbox/kie/kie/model.safetensors → zip 展開 → OLD mtime 最新）"
python - <<'PY'
from pathlib import Path
import shutil, time
root=Path("."); inbox=root/"artifacts_inbox"; staged=root/"data/staged_project"; out=root/"kie/kie/model.safetensors"
cands=[]
# 1) 直接優先
for p in [inbox/"kie/kie/model.safetensors", inbox/"kie/model.safetensors"]:
    if p.exists(): cands.append(p)
# 2) zip 展開的權重
for p in staged.rglob("model.safetensors"):
    cands.append(p)
# 3) 舊專案
OLD=Path.home()/ "projects/smart-mail-agent"
for p in OLD.rglob("model.safetensors"):
    cands.append(p)
if cands:
    pick=max(cands, key=lambda p: p.stat().st_mtime)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists(): shutil.copy2(out, out.with_suffix(out.suffix+f".bak_{time.strftime('%Y%m%dT%H%M%S')}"))
    shutil.copy2(pick, out)
    print("[APPLY] KIE ->", out, "(from:", pick, ")")
else:
    print("[WARN] 沒找到 model.safetensors，略過覆蓋")
PY

log "[STEP5] 遞迴掃描並組合 Spam / Intent 評測集（多來源去重；容錯跳過壞行）"
python - <<'PY'
import json, hashlib, re, os
from pathlib import Path

def sha1(s): 
    return hashlib.sha1((s or "").strip().encode("utf-8")).hexdigest()

def get_text(r):
    for a,b in [("subject","body"),("title","content")]:
        if r.get(a) or r.get(b): return ("{} {}".format(r.get(a,""),r.get(b,""))).strip()
    for k in ["text","content","message","raw","description","body","subject"]:
        if r.get(k): return str(r[k]).strip()
    for k in ["email","mail","data","record","sample"]:
        obj=r.get(k)
        if isinstance(obj,dict):
            for kk in ["text","content","body","subject","message"]:
                if obj.get(kk): return str(obj[kk]).strip()
    return ""

def norm_spam(y):
    if y is None: return None
    if isinstance(y,(int,float)): return 1 if int(y)!=0 else 0
    s=str(y).strip().lower()
    if s in {"1","true","yes","spam","phish","phishing"}: return 1
    if s in {"0","false","no","ham"}: return 0
    return None

root=Path(".")
# ---- Spam sources（固定 + staged 遞迴）----
fixed_spam = [
    "data/benchmarks/spamassassin.jsonl",
    "data/benchmarks/spamassassin.clean.jsonl",
    "data/benchmarks/spamassassin_phish.jsonl",
    "data/spam_sa/test.jsonl",
    "data/prod_merged/test.jsonl",
    "data/trec06c_zip/test.jsonl",
]
spam_paths=[Path(p) for p in fixed_spam if Path(p).exists()]
# 再把 staged_project / artifacts_inbox 裡任何含 spam 關鍵字的 jsonl/ndjson 也掃進來
for base in [root/"data/staged_project", root/"artifacts_inbox"]:
    if base.exists():
        for p in base.rglob("*.jsonl"):
            if "spam" in p.name.lower(): spam_paths.append(p)
        for p in base.rglob("*.ndjson"):
            if "spam" in p.name.lower(): spam_paths.append(p)

spam_rows=[]; seen=set(); used=[]
for p in spam_paths:
    ok=bad=0
    for ln in p.read_text("utf-8",errors="ignore").splitlines():
        try:
            if not ln.strip(): continue
            r=json.loads(ln)
            y = norm_spam( r.get("spam") if "spam" in r else (r.get("label") or r.get("target")) )
            if y is None: continue
            t=get_text(r)
            if not t: continue
            k=sha1(t)
            if k in seen: continue
            seen.add(k); spam_rows.append({"text":t,"spam":int(y)}); ok+=1
        except Exception:
            bad+=1
    used.append((str(p),ok,bad))
Path("data/spam_eval").mkdir(parents=True, exist_ok=True)
Path("data/spam_eval/dataset.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in spam_rows),"utf-8")
print("[SPAM] sources_used:"); 
for p,ok,bad in used: print(f" - {p} ok={ok} bad={bad}")
print(f"[OK] spam_eval -> data/spam_eval/dataset.jsonl size={len(spam_rows)}")

# ---- Intent sources（遞迴掃描所有 jsonl/ndjson/json，挑出有標籤 & 文本的）----
en2zh={
 "biz_quote":"報價","quote":"報價","pricing":"報價","sales_quote":"報價","estimate":"報價","quotation":"報價",
 "tech_support":"技術支援","support":"技術支援","bug":"技術支援","issue":"技術支援","ticket":"技術支援",
 "complaint":"投訴","refund":"投訴","chargeback":"投訴","return":"投訴","claim":"投訴",
 "policy_qa":"規則詢問","faq":"規則詢問","policy":"規則詢問","terms":"規則詢問","sla":"規則詢問",
 "profile_update":"資料異動","account_update":"資料異動","change_request":"資料異動","update":"資料異動","profile":"資料異動",
 "other":"其他","misc":"其他","general":"其他"
}
zh_set={"報價","技術支援","投訴","規則詢問","資料異動","其他"}
label_keys=("intent","label","category","class","y","target","label_str","label_text","label_name","intent_label","intent_name","tag","y_true","gt","ground_truth")
nested_keys=[("gold","intent"),("anno","intent"),("gold","label"),("annotation","intent")]
zh_syn = {
 "報價": {"報價","問價","價錢","價格","估價","報價單","quotation","quote","pricing","estimate"},
 "技術支援": {"技術支援","技支","bug","錯誤","無法","失敗","壞掉","異常","報錯","error","stacktrace"},
 "投訴": {"投訴","客訴","抱怨","不滿","退款","退費","賠償","延遲","慢","退單","毀損","缺件","少寄","寄錯","沒收到","沒出貨","無回覆","拖延"},
 "規則詢問": {"規則詢問","SLA","條款","合約","政策","policy","流程","SOP","FAQ"},
 "資料異動": {"資料異動","更改","修改","變更","更新","地址","電話","email","帳號","個資","profile"},
 "其他": {"其他","一般","misc","general"}
}
def map_intent(v):
    if v is None: return None
    if isinstance(v, dict):
        for kk in ["zh","cn","zh_tw","text","name","label"]:
            if v.get(kk): return map_intent(v[kk])
        return None
    s=str(v).strip()
    if s in zh_set: return s
    low=s.lower()
    if low in en2zh: return en2zh[low]
    for tgt,bag in zh_syn.items():
        for w in bag:
            if w.lower() in low: return tgt
    return None

def walk_json_candidates(base:Path):
    for ext in ("*.jsonl","*.ndjson","*.json"):
        for p in base.rglob(ext):
            yield p

intent_paths=[]
for base in [Path("data/intent_eval"), Path("data/staged_project"), Path("artifacts_inbox")]:
    if base.exists():
        intent_paths += [p for p in walk_json_candidates(base)]
# 舊專案常見位置
op = Path.home()/ "projects/smart-mail-agent"
for rel in ["data/intent_eval/dataset.jsonl","reports_auto/intent/test.jsonl","reports_auto/intent/val.jsonl","reports_auto/intent/train.jsonl"]:
    pp = op/rel
    if pp.exists(): intent_paths.append(pp)

# 去重路徑
seenp=set(); uniq=[]
for p in intent_paths:
    s=str(p.resolve())
    if s in seenp: continue
    seenp.add(s); uniq.append(p)
intent_paths=uniq

rows=[]; seen=set(); used_i=[]; by_label={}
for p in intent_paths:
    ok=bad=0
    try:
        payload=p.read_text("utf-8",errors="ignore")
    except Exception:
        continue
    # JSONL or single JSON array/object
    lines = payload.splitlines()
    if len(lines)<=3 and payload.strip().startswith("["):
        # JSON array
        try:
            import json as _json
            arr=_json.loads(payload)
            lines=[_json.dumps(x,ensure_ascii=False) for x in (arr if isinstance(arr,list) else [arr])]
        except Exception:
            pass
    for ln in lines:
        try:
            ln=ln.strip()
            if not ln or ln in {"[","]","{","}"}: continue
            r=json.loads(ln)
            t=get_text(r)
            if not t: continue
            lab=None
            for k in label_keys:
                if k in r:
                    lab=map_intent(r[k]); 
                    if lab: break
            if not lab:
                for a,b in nested_keys:
                    x=r.get(a); 
                    if isinstance(x,dict) and b in x:
                        lab=map_intent(x[b]); 
                        if lab: break
            if not lab: 
                continue
            k=sha1(t)
            if k in seen: continue
            seen.add(k); rows.append({"text":t,"intent":lab}); ok+=1
            by_label[lab]=by_label.get(lab,0)+1
        except Exception:
            bad+=1
    used_i.append((str(p),ok,bad))
Path("data/intent_eval").mkdir(parents=True, exist_ok=True)
Path("data/intent_eval/dataset.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in rows),"utf-8")
print("[INTENT] sources_used:"); 
for p,ok,bad in used_i: print(f" - {p} ok={ok} bad={bad}")
print(f"[OK] intent_eval -> data/intent_eval/dataset.jsonl size={len(rows)}")
print("[INTENT] label_dist:", json.dumps(by_label, ensure_ascii=False))
PY

log "[STEP6] 跑 evaluator（若腳本存在且資料非空）"
[ -s data/spam_eval/dataset.jsonl ]  && [ -x sma_oneclick_eval.sh ] && { echo "[INFO] dataset=data/spam_eval"; bash sma_oneclick_eval.sh data/spam_eval || true; } || echo "[INFO] 略過 spam eval（無資料或無腳本）"
[ -s data/intent_eval/dataset.jsonl ] && [ -x sma_oneclick_eval.sh ] && { echo "[INFO] dataset=data/intent_eval"; bash sma_oneclick_eval.sh data/intent_eval || true; } || echo "[INFO] 略過 intent eval（無資料或無腳本）"

log "[STEP7] 自算 Intent『門檻+規則』macro-F1（就算 evaluator 沒生檔也能出表）"
python - <<'PY'
import json, re, sys, types, pickle, math
from pathlib import Path
root=Path("."); ds_p = root/"data/intent_eval/dataset.jsonl"
if not ds_p.exists() or ds_p.stat().st_size==0:
    print("[WARN] intent_eval 空，跳過 rules+threshold 指標"); raise SystemExit(0)
ds=[json.loads(x) for x in ds_p.read_text("utf-8").splitlines() if x.strip()]
texts=[r.get("text") or "" for r in ds]
gold=[r.get("intent") for r in ds]
th_p = root/"reports_auto/intent_thresholds.json"
th = json.loads(th_p.read_text("utf-8")) if th_p.exists() else {"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3}

def builtins_rules():
    pat={
     "投訴": r"(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)",
     "報價": r"(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)",
     "技術支援": r"(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)",
     "規則詢問": r"(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)",
     "資料異動": r"(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)"
    }
    pri=["投訴","報價","技術支援","規則詢問","資料異動"]
    return pri,{k:re.compile(v,re.I) for k,v in pat.items()}

rx_file = root/"configs/intent_rules_compiled.json"
if rx_file.exists():
    j=json.loads(rx_file.read_text("utf-8"))
    pri=j.get("priority") or ["投訴","報價","技術支援","規則詢問","資料異動"]
    RX={k:re.compile(v,re.I) for k,v in (j.get("patterns") or {}).items()}
else:
    pri,RX = builtins_rules()
def rule_pick(t:str):
    for lab in pri:
        r=RX.get(lab)
        if r and r.search(t or ""): return lab
    return None

def inject_main_rules_feat():
    from smart_mail_agent.ml.rules_feat import rules_feat as _rf
    m = sys.modules.get("__main__") or types.ModuleType("__main__")
    setattr(m,"rules_feat",_rf); sys.modules["__main__"]=m
inject_main_rules_feat()

model=None
for p in ["artifacts/intent_pro_cal.pkl","artifacts/intent_pipeline_fixed.pkl","artifacts/intent_clf.pkl"]:
    pp=Path(p)
    if not pp.exists(): continue
    try:
        try:
            import joblib; model=joblib.load(pp)
        except Exception:
            model=pickle.loads(pp.read_bytes())
        print("[OK] loaded intent model:", p); break
    except Exception as e:
        print("[WARN] load fail", p, "->", e)

def softmax(arr):
    m=max(arr); ex=[math.exp(x-m) for x in arr]; s=sum(ex); 
    return [e/(s or 1.0) for e in ex]

def map2zh(lbl):
    mp={"biz_quote":"報價","quote":"報價","pricing":"報價","sales_quote":"報價",
        "tech_support":"技術支援","support":"技術支援","bug":"技術支援","issue":"技術支援",
        "complaint":"投訴","refund":"投訴","chargeback":"投訴","return":"投訴",
        "policy_qa":"規則詢問","faq":"規則詢問","policy":"規則詢問","terms":"規則詢問","sla":"規則詢問",
        "profile_update":"資料異動","account_update":"資料異動","change_request":"資料異動","update":"資料異動",
        "other":"其他","misc":"其他","general":"其他"}
    s=str(lbl).strip().lower(); 
    return mp.get(s, "其他") if s not in {"報價","技術支援","投訴","規則詢問","資料異動","其他"} else s

pred_final=[]
if model:
    classes = getattr(model,'classes_',None)
    def pred_one(t):
        try:
            if hasattr(model,"predict_proba"):
                prob=model.predict_proba([t])[0]; idx=int(max(range(len(prob)), key=lambda i: prob[i])); conf=float(prob[idx])
                lab = map2zh(classes[idx] if classes is not None else idx)
            elif hasattr(model,"decision_function"):
                sc=model.decision_function([t])[0]
                if hasattr(sc,'__len__'):
                    pr=softmax(list(sc)); idx=int(max(range(len(pr)), key=lambda i: pr[i])); conf=float(pr[idx])
                else:
                    conf=1/(1+math.exp(-float(sc))); idx=0
                lab = map2zh(classes[idx] if classes is not None else idx)
            else:
                lab = map2zh(model.predict([t])[0]); conf=0.5
        except Exception:
            lab=None; conf=0.0
        thr = th.get(lab, th.get("其他",0.4))
        routed = lab
        r=rule_pick(t)
        if lab is None or conf < thr:
            routed = r or "其他"
        else:
            if r and r!=lab: routed=r
        return routed
    pred_final=[pred_one(t) for t in texts]
else:
    pred_final=[rule_pick(t) or "其他" for t in texts]

labels=sorted(list(set(gold) | set(pred_final) | set(th.keys())))
cm={lab:{"tp":0,"fp":0,"fn":0} for lab in labels}
for g,p in zip(gold,pred_final):
    if p==g: cm[g]["tp"]+=1
    else: cm[p]["fp"]+=1; cm[g]["fn"]+=1

def prf(m): 
    tp,fp,fn=m["tp"],m["fp"]
    P=tp/(tp+fp) if (tp+fp)>0 else 0.0
    R=tp/(tp+m.get("fn",0)) if (tp+m.get("fn",0))>0 else 0.0
    F1=2*P*R/(P+R) if (P+R)>0 else 0.0
    return P,R,F1

rows=[]; mf=0.0
for lab in labels:
    P,R,F1=prf(cm[lab]); rows.append((lab,P,R,F1,cm[lab]["tp"],cm[lab]["fp"],cm[lab]["fn"]))
    mf+=F1
mf/=len(labels) if labels else 0.0

out_dir = sorted([p for p in (root/"reports_auto/eval").glob("*") if p.is_dir()], key=lambda p:p.stat().st_mtime)
out_dir = out_dir[-1] if out_dir else (root/"reports_auto/eval/INTENT_RULES_"+__import__("time").strftime("%Y%m%dT%H%M%S"))
out_dir.mkdir(parents=True, exist_ok=True)
md = ["# Intent metrics (threshold + rules)",
      f"- thresholds: {json.dumps(th,ensure_ascii=False)}",
      f"- macro_f1_after_threshold_and_rules: {mf:.3f}",
      "",
      "|label|P|R|F1|TP|FP|FN|",
      "|---|---:|---:|---:|---:|---:|---:|"]
for lab,Pv,Rv,F1,TP,FP,FN in rows:
    md.append(f"|{lab}|{Pv:.3f}|{Rv:.3f}|{F1:.3f}|{TP}|{FP}|{FN}|")
(out_dir/"metrics_after_threshold_and_rules.md").write_text("\n".join(md),"utf-8")
print("[OK] wrote", out_dir/"metrics_after_threshold_and_rules.md")
PY

log "[STEP8] 收集 KIE 離線評測附件到 reports_auto/kie_eval 並掛到摘要"
collect_from(){ d="$1"; [ -d "$d" ] || return 0; for p in "$d"/kie_eval_*.txt "$d"/kie_fields_*.txt "$d"/kie_pred*.jsonl; do [ -f "$p" ] && cp -f "$p" "$KIE_EVAL_DIR/"; done; }
collect_from "$INBOX"; collect_from "$STAGED"; collect_from "$OLD"

{
  echo "# ONECLICK v11 (${TS})"
  echo "## Artifacts"
  echo '```'
  ls -l artifacts_prod 2>/dev/null || true
  ls -l artifacts 2>/dev/null || true
  echo; ls -l kie/kie 2>/dev/null || true
  echo '```'
  echo "## Datasets"
  echo "- spam_eval rows: $(wc -l < data/spam_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo "- intent_eval rows: $(wc -l < data/intent_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo "## Latest Eval dir"
  last_eval="$(ls -1dt reports_auto/eval/* 2>/dev/null | head -n1 || true)"
  [ -n "$last_eval" ] && echo "- $last_eval" || echo "- (none)"
  echo "## Intent(threshold+rules) metrics"
  [ -n "$last_eval" ] && [ -f "$last_eval/metrics_after_threshold_and_rules.md" ] && sed -n '1,160p' "$last_eval/metrics_after_threshold_and_rules.md" || echo "(no file)"
  echo "## KIE 離線評測附件（@ reports_auto/kie_eval）"
  ls -1 "$KIE_EVAL_DIR" 2>/dev/null | sed 's/^/- /' || echo "- (無)"
} > "$SUMMARY"

log "[DONE] Summary -> $SUMMARY"
