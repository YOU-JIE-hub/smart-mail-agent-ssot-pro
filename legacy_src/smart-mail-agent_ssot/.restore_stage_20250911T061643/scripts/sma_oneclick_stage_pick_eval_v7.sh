#!/usr/bin/env bash
# 入倉 spam/intent → KIE 權重優先 artifacts_inbox → 組評測集(多來源去重+容錯)
# → 跑 eval（若有）→ Intent(門檻+規則) 自算 → 掛 KIE 附件 → 摘要
set -o pipefail
OLD="/home/youjie/projects/smart-mail-agent"
NEW="/home/youjie/projects/smart-mail-agent_ssot"
INBOX="$NEW/artifacts_inbox"
TS="$(date +%Y%m%dT%H%M%S)"
STATUS_DIR="$NEW/reports_auto/status"
ERR_DIR="$NEW/reports_auto/errors"
EVAL_DIR="$NEW/reports_auto/eval"
KIE_EVAL_DIR="$NEW/reports_auto/kie_eval"
LOG="$ERR_DIR/ONECLICK_v7_${TS}.log"
SUMMARY="$STATUS_DIR/ONECLICK_v7_${TS}.md"

mkdir -p "$STATUS_DIR" "$ERR_DIR" "$KIE_EVAL_DIR" \
         "$NEW/artifacts_prod" "$NEW/artifacts" "$NEW/kie/kie" \
         "$NEW/data/spam_eval" "$NEW/data/intent_eval" \
         "$NEW/src/smart_mail_agent/ml" "$NEW/configs"

log(){ printf '%s\n' "$*" | tee -a "$LOG" >&2; }

cd "$NEW" 2>/dev/null || { echo "[FATAL] NEW 專案不存在：$NEW"; exit 2; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:src:scripts:.sma_tools:${PYTHONPATH:-}"

log "[STEP0] 建 shim（legacy intent pickles 需要 rules_feat）"
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

log "[STEP1] 入倉 spam/intent（優先 artifacts_inbox，其次 /mnt/data）"
stage_one(){ src="$1"; dst="$2"; [ -f "$src" ] && { cp -f "$src" "$dst"; log "  staged $(basename "$src") -> $dst"; }; }
# spam
stage_one "$INBOX/model_pipeline.pkl"   "artifacts_prod/model_pipeline.pkl"
stage_one "$INBOX/ens_thresholds.json"  "artifacts_prod/ens_thresholds.json"
stage_one "$INBOX/model_meta.json"      "artifacts_prod/model_meta.json"
stage_one "$INBOX/spam_rules.json"      "artifacts_prod/spam_rules.json"
stage_one "/mnt/data/model_pipeline.pkl"   "artifacts_prod/model_pipeline.pkl"
stage_one "/mnt/data/ens_thresholds.json"  "artifacts_prod/ens_thresholds.json"
stage_one "/mnt/data/model_meta.json"      "artifacts_prod/model_meta.json"
stage_one "/mnt/data/spam_rules.json"      "artifacts_prod/spam_rules.json" || true
# intent
stage_one "$INBOX/intent_pro_cal.pkl"        "artifacts/intent_pro_cal.pkl"
stage_one "$INBOX/intent_pipeline_fixed.pkl" "artifacts/intent_pipeline_fixed.pkl"
stage_one "$INBOX/intent_clf.pkl"            "artifacts/intent_clf.pkl"
stage_one "/mnt/data/intent_pro_cal.pkl"        "artifacts/intent_pro_cal.pkl"
stage_one "/mnt/data/intent_pipeline_fixed.pkl" "artifacts/intent_pipeline_fixed.pkl"
stage_one "/mnt/data/intent_clf.pkl"            "artifacts/intent_clf.pkl"
stage_one "$INBOX/intent_rules.json"         "configs/intent_rules.json"
stage_one "/mnt/data/intent_rules.json"      "configs/intent_rules.json"

log "[STEP2] 標準化門檻 + 編譯 intent 規則"
python - <<'PY'
import json, pathlib, re, sys
root=pathlib.Path(".")
# spam thresholds -> {"spam": float}
p=root/"artifacts_prod/ens_thresholds.json"
if p.exists():
    try:
        j=json.loads(p.read_text("utf-8"))
        thr=j.get("spam") if isinstance(j.get("spam"),(int,float)) else (j.get("threshold") or 0.44)
        p.write_text(json.dumps({"spam":float(thr)},ensure_ascii=False,indent=2),"utf-8")
        print("[OK] spam thresholds ->", float(thr))
    except Exception as e:
        print("[WARN] bad ens_thresholds.json:", e)
        p.write_text(json.dumps({"spam":0.44},ensure_ascii=False,indent=2),"utf-8")
else:
    p.write_text(json.dumps({"spam":0.44},ensure_ascii=False,indent=2),"utf-8")
    print("[OK] spam thresholds -> default 0.44")

# intent thresholds default 若缺
it=root/"reports_auto/intent_thresholds.json"
if not it.exists():
    it.write_text(json.dumps({"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3},ensure_ascii=False,indent=2),"utf-8")
    print("[OK] intent thresholds -> default")

# 編譯 intent 規則
ir = root/"configs/intent_rules.json"
if ir.exists():
    try:
        j=json.loads(ir.read_text("utf-8"))
        rx={}
        for k,v in j.items():
            if isinstance(v,str): rx[k]=v
            elif isinstance(v,(list,tuple)):
                rx[k]="("+"|".join(map(re.escape,v))+")"
        out={"priority":["投訴","報價","技術支援","規則詢問","資料異動","其他"],"patterns":rx}
        (root/"configs/intent_rules_compiled.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
        print("[OK] compiled intent rules -> configs/intent_rules_compiled.json")
    except Exception as e:
        print("[WARN] intent_rules.json parse fail:", e, "; will use built-ins")
else:
    print("[INFO] no intent_rules.json; will use built-ins if needed")
PY

log "[STEP3] 挑 KIE 權重（優先 artifacts_inbox/kie/kie/model.safetensors，其次 OLD 最新）"
PREF="$INBOX/kie/kie/model.safetensors"
if [ -f "$PREF" ]; then
  cp -f "$PREF" "kie/kie/model.safetensors"
  log "[APPLY] KIE -> kie/kie/model.safetensors (from artifacts_inbox)"
else
  # 從 OLD 尋找最新 model.safetensors
  CAND="$(find "$OLD" -type f -name model.safetensors -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1{print $2}')"
  if [ -n "$CAND" ] && [ -f "$CAND" ]; then
    cp -f "$CAND" "kie/kie/model.safetensors"
    log "[APPLY] KIE -> kie/kie/model.safetensors (from $CAND)"
  else
    log "[WARN] 找不到 KIE 權重，略過覆蓋"
  fi
fi

log "[STEP4] 組合 Spam / Intent 評測集（多來源去重；容錯跳過壞行）"
python - <<'PY'
import json, hashlib, re, os
from pathlib import Path

def sha1(s): return hashlib.sha1((s or "").strip().encode("utf-8")).hexdigest()
def norm_spam(y):
    if y is None: return None
    if isinstance(y,(int,float)): return 1 if int(y)!=0 else 0
    s=str(y).strip().lower()
    if s in {"1","true","yes","spam","phish","phishing"}: return 1
    if s in {"0","false","no","ham"}: return 0
    return None
def text_of(r): return r.get("text") or r.get("body") or r.get("subject") or ""

root=Path(".")
# --- Spam sources ---
spam_src = [
    # NEW
    "data/benchmarks/spamassassin.jsonl",
    "data/benchmarks/spamassassin.clean.jsonl",
    "data/benchmarks/spamassassin_phish.jsonl",
    "data/spam_sa/test.jsonl",
    "data/prod_merged/test.jsonl",
    "data/trec06c_zip/test.jsonl",
    # /mnt/data
    "/mnt/data/spamassassin.jsonl",
    "/mnt/data/spamassassin.clean.jsonl",
    "/mnt/data/spamassassin_phish.jsonl",
    "/mnt/data/external_realistic_test.clean.jsonl",
    # OLD
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.clean.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin_phish.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/spam_sa/test.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/prod_merged/test.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/trec06c_zip/test.jsonl",
]
spam_rows=[]; seen=set(); used=[]
for p in spam_src:
    try:
        raw = Path(p).read_text("utf-8", errors="ignore").splitlines()
    except Exception:
        continue
    ok=bad=0
    for ln in raw:
        try:
            if not ln.strip(): continue
            r=json.loads(ln)
            y = norm_spam(r.get("spam") if "spam" in r else r.get("label"))
            if y is None: continue
            t=text_of(r).strip()
            if not t: continue
            k=sha1(t)
            if k in seen: continue
            seen.add(k); spam_rows.append({"text":t,"spam":int(y)}); ok+=1
        except Exception:
            bad+=1
    used.append((p,ok,bad))
Path("data/spam_eval").mkdir(parents=True, exist_ok=True)
Path("data/spam_eval/dataset.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in spam_rows),"utf-8")
print("[SPAM] sources_used:"); 
for p,ok,bad in used: print(f" - {p} ok={ok} bad={bad}")
print(f"[OK] spam_eval -> data/spam_eval/dataset.jsonl size={len(spam_rows)}")

# --- Intent sources ---
en2zh={
 "biz_quote":"報價","quote":"報價","pricing":"報價","sales_quote":"報價",
 "tech_support":"技術支援","support":"技術支援","bug":"技術支援","issue":"技術支援",
 "complaint":"投訴","refund":"投訴","chargeback":"投訴","return":"投訴",
 "policy_qa":"規則詢問","faq":"規則詢問","policy":"規則詢問","terms":"規則詢問","sla":"規則詢問",
 "profile_update":"資料異動","account_update":"資料異動","change_request":"資料異動","update":"資料異動",
 "other":"其他","misc":"其他","general":"其他"
}
zh_set={"報價","技術支援","投訴","規則詢問","資料異動","其他"}
def map_intent(lbl):
    if lbl is None: return None
    if isinstance(lbl,str):
        s=lbl.strip()
        if s in zh_set: return s
        t=s.lower()
        return en2zh.get(t, None)
    return None

intent_src = [
    # /mnt/data
    "/mnt/data/test_labeled.jsonl",
    "/mnt/data/test.jsonl",
    "/mnt/data/test.sample.jsonl",
    "/mnt/data/test.demo.jsonl",
    "/mnt/data/test_real.jsonl",
    "/mnt/data/val.jsonl",
    "/mnt/data/gold_for_train.jsonl",
    # NEW
    "data/intent_eval/dataset.jsonl",   # 若已有就拿來補
    # OLD（若有舊標註）
    "/home/youjie/projects/smart-mail-agent/data/intent_eval/dataset.jsonl",
]
rows=[]; seen=set(); used_i=[]
for p in intent_src:
    try:
        raw=Path(p).read_text("utf-8", errors="ignore").splitlines()
    except Exception:
        continue
    ok=bad=0
    for ln in raw:
        try:
            if not ln.strip(): continue
            r=json.loads(ln)
            t=text_of(r).strip()
            if not t: continue
            lbl = r.get("intent") or r.get("label")
            lbl = map_intent(lbl)
            if not lbl: continue
            k=sha1(t)
            if k in seen: continue
            seen.add(k); rows.append({"text":t,"intent":lbl}); ok+=1
        except Exception:
            bad+=1
    used_i.append((p,ok,bad))
Path("data/intent_eval").mkdir(parents=True, exist_ok=True)
Path("data/intent_eval/dataset.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in rows),"utf-8")
print("[INTENT] sources_used:"); 
for p,ok,bad in used_i: print(f" - {p} ok={ok} bad={bad}")
print(f"[OK] intent_eval -> data/intent_eval/dataset.jsonl size={len(rows)}")
PY

log "[STEP5] 跑 evaluator（若腳本存在且資料非空）"
[ -s data/spam_eval/dataset.jsonl ]  && [ -x sma_oneclick_eval.sh ] && { echo "[INFO] dataset=data/spam_eval"; bash sma_oneclick_eval.sh data/spam_eval || true; } || echo "[INFO] 略過 spam eval（無資料或無腳本）"
[ -s data/intent_eval/dataset.jsonl ] && [ -x sma_oneclick_eval.sh ] && { echo "[INFO] dataset=data/intent_eval"; bash sma_oneclick_eval.sh data/intent_eval || true; } || echo "[INFO] 略過 intent eval（無資料或無腳本）"

log "[STEP6] 自行計算 Intent『門檻+規則』macro-F1（用模型，失敗則 rules-only）"
python - <<'PY'
import json, re, sys, types, pickle, math
from pathlib import Path

root=Path(".")
ds_p = root/"data/intent_eval/dataset.jsonl"
if not ds_p.exists() or ds_p.stat().st_size==0:
    print("[WARN] intent_eval 空，跳過 rules+threshold 指標"); raise SystemExit(0)
ds=[json.loads(x) for x in ds_p.read_text("utf-8").splitlines() if x.strip()]
texts=[r.get("text") or "" for r in ds]
gold=[r.get("intent") for r in ds]

# thresholds
th_p = root/"reports_auto/intent_thresholds.json"
th = json.loads(th_p.read_text("utf-8")) if th_p.exists() else {"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3}

# rules
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

# 嘗試載入模型（artifacts/intent_pro_cal.pkl -> intent_pipeline_fixed.pkl -> intent_clf.pkl）
model=None; model_path=None; errs=[]
def inject_main_rules_feat():
    from smart_mail_agent.ml.rules_feat import rules_feat as _rf
    m = sys.modules.get("__main__") or types.ModuleType("__main__")
    setattr(m,"rules_feat",_rf)
    sys.modules["__main__"]=m
inject_main_rules_feat()
for p in ["artifacts/intent_pro_cal.pkl","artifacts/intent_pipeline_fixed.pkl","artifacts/intent_clf.pkl"]:
    pp=Path(p)
    if not pp.exists(): continue
    try:
        try:
            import joblib
            model=joblib.load(pp)
        except Exception:
            with open(pp,"rb") as f: model=pickle.load(f)
        model_path=p; break
    except Exception as e:
        errs.append(f"{p}: {e}")

def softmax(x):
    if hasattr(x,"ndim") and x.ndim==1:
        m=max(x); ex=[math.exp(a-m) for a in x]; s=sum(ex); 
        return [e/(s or 1.0) for e in ex]
    return x

# label 映射
en2zh={"biz_quote":"報價","quote":"報價","pricing":"報價","sales_quote":"報價",
       "tech_support":"技術支援","support":"技術支援","bug":"技術支援","issue":"技術支援",
       "complaint":"投訴","refund":"投訴","chargeback":"投訴","return":"投訴",
       "policy_qa":"規則詢問","faq":"規則詢問","policy":"規則詢問","terms":"規則詢問","sla":"規則詢問",
       "profile_update":"資料異動","account_update":"資料異動","change_request":"資料異動","update":"資料異動",
       "other":"其他","misc":"其他","general":"其他"}
zh_set=set(["報價","技術支援","投訴","規則詢問","資料異動","其他"])
def map2zh(lbl):
    if lbl in zh_set: return lbl
    s=str(lbl).lower()
    return en2zh.get(s,"其他")

# 推論（若模型可用）＋門檻+規則路由
pred_final=[]; classes=[]
if model is not None:
    # 盡力拿 classes_
    classes = getattr(getattr(model,'classes_',None),'tolist',lambda: getattr(model,'classes_',None))()
    if classes is None and hasattr(model,'classes_'):
        classes=list(model.classes_)
    def pred_one(t):
        x=[t]
        try:
            if hasattr(model,"predict_proba"):
                proba=model.predict_proba(x)[0]
                labs = [map2zh(c) for c in getattr(model,"classes_",list(range(len(proba))))]
                idx = int(max(range(len(proba)), key=lambda i: proba[i]))
                pred = labs[idx]; conf=float(proba[idx])
            elif hasattr(model,"decision_function"):
                s=model.decision_function(x)[0]
                try: 
                    it=list(s); pr=softmax(it); idx=int(max(range(len(pr)), key=lambda i: pr[i])); conf=float(pr[idx])
                except Exception:
                    # 二分類情況
                    val=float(s if not hasattr(s,'__len__') else s[0])
                    conf=1/(1+math.exp(-val)); idx=0
                labs = getattr(model,"classes_",["其他"])
                pred = map2zh(labs[idx] if hasattr(labs,'__getitem__') else labs)
            elif hasattr(model,"predict"):
                y=model.predict(x)[0]; pred=map2zh(y); conf=0.5
            else:
                raise RuntimeError("model has no predict*")
        except Exception:
            pred=None; conf=0.0
        # 門檻+規則
        thr = th.get(pred, th.get("其他",0.4))
        routed = pred
        r = rule_pick(t)
        if pred is None or conf < thr:
            routed = r or "其他"
        else:
            if r and r!=pred: routed=r
        return routed
    for t in texts:
        pred_final.append(pred_one(t))
else:
    # 無模型，rules-only
    pred_final=[rule_pick(t) or "其他" for t in texts]

# 計算指標
labels=sorted(list(set(gold) | set(pred_final) | set(th.keys())))
cm={lab:{"tp":0,"fp":0,"fn":0} for lab in labels}
for g,p in zip(gold,pred_final):
    if p==g: cm[g]["tp"]+=1
    else: cm[p]["fp"]+=1; cm[g]["fn"]+=1
def prf(a):
    tp,fp,fn=a["tp"],a["fp"],a["fn"]
    P = (tp/(tp+fp)) if (tp+fp)>0 else 0.0
    R = (tp/(tp+fn)) if (tp+fn)>0 else 0.0
    F1 = (2*P*R/(P+R)) if (P+R)>0 else 0.0
    return P,R,F1
rows=[]; mf=0.0
for lab in labels:
    P,R,F1=prf(cm[lab]); rows.append((lab,P,R,F1,cm[lab]["tp"],cm[lab]["fp"],cm[lab]["fn"])); mf+=F1
mf = mf/len(labels) if labels else 0.0

# 落檔到最新 eval 目錄（若存在），否則新建一個
eval_dirs=sorted([p for p in (root/"reports_auto/eval").glob("*") if p.is_dir()], key=lambda p:p.stat().st_mtime)
out_dir = eval_dirs[-1] if eval_dirs else (root/"reports_auto/eval/INTENT_RULES_"+__import__("time").strftime("%Y%m%dT%H%M%S"))
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

log "[STEP7] 收集 KIE 離線評測附件到 reports_auto/kie_eval 並掛到摘要"
# 從 /mnt/data 與 artifacts_inbox 蒐集 KIE 文字/JSONL 證據
collect_one(){ for p in "$1"/kie_eval_*.txt "$1"/kie_fields_*.txt "$1"/kie_pred*.jsonl; do [ -f "$p" ] && cp -f "$p" "$KIE_EVAL_DIR/"; done; }
collect_one "/mnt/data"
collect_one "$INBOX"
# 摘要
{
  echo "# ONECLICK v7 (${TS})"
  echo "## Artifacts"
  echo "\`\`\`"
  ls -l artifacts_prod 2>/dev/null || true
  ls -l artifacts 2>/dev/null || true
  echo; ls -l kie/kie 2>/dev/null || true
  echo "\`\`\`"
  echo "## Datasets"
  echo "- spam_eval rows: $(wc -l < data/spam_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo "- intent_eval rows: $(wc -l < data/intent_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo "## Latest Eval dir"
  last_eval="$(ls -1dt reports_auto/eval/* 2>/dev/null | head -n1 || true)"
  [ -n "$last_eval" ] && echo "- $last_eval" || echo "- (none)"
  echo "## Intent(threshold+rules) metrics"
  [ -n "$last_eval" ] && sed -n '1,80p' "$last_eval/metrics_after_threshold_and_rules.md" 2>/dev/null || echo "(no file)"
  echo "## KIE 離線評測附件（@ reports_auto/kie_eval）"
  ls -1 "$KIE_EVAL_DIR" 2>/dev/null | sed 's/^/- /' || echo "- (無)"
} > "$SUMMARY"

log "[DONE] Summary -> $SUMMARY"
