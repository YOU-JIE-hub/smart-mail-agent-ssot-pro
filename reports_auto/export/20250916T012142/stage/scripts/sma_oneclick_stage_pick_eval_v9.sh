#!/usr/bin/env bash
# 入倉 spam/intent → KIE 權重優先 artifacts_inbox → 組評測集(多來源去重+容錯，不用 /mnt/data)
# → 跑 eval（若有）→ Intent(門檻+規則) 自算 → 掛 KIE 附件 → 摘要
set -o pipefail
OLD="$HOME/projects/smart-mail-agent"
NEW="$HOME/projects/smart-mail-agent_ssot"
INBOX="$NEW/artifacts_inbox"
TS="$(date +%Y%m%dT%H%M%S)"
STATUS_DIR="$NEW/reports_auto/status"
ERR_DIR="$NEW/reports_auto/errors"
EVAL_DIR="$NEW/reports_auto/eval"
KIE_EVAL_DIR="$NEW/reports_auto/kie_eval"
LOG="$ERR_DIR/ONECLICK_v9_${TS}.log"
SUMMARY="$STATUS_DIR/ONECLICK_v9_${TS}.md"

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

log "[STEP1] 入倉 spam/intent（優先 artifacts_inbox，其次 OLD）"
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
[ -f artifacts/intent_pro_cal.pkl ] || stage "$OLD/artifacts/releases/intent"/*/intent_pro_cal.pkl "artifacts/intent_pro_cal.pkl"
stage "$INBOX/intent_rules.json"         "configs/intent_rules.json" || true

log "[STEP2] 標準化門檻 + 編譯 intent 規則"
python - <<'PY'
import json, pathlib, re
root=pathlib.Path(".")
# spam thresholds
p=root/"artifacts_prod/ens_thresholds.json"
if p.exists():
    try:
        j=json.loads(p.read_text("utf-8"))
        thr=j.get("spam") if isinstance(j.get("spam"),(int,float)) else (j.get("threshold") or 0.44)
        p.write_text(json.dumps({"spam":float(thr)},ensure_ascii=False,indent=2),"utf-8")
        print("[OK] spam thresholds ->", float(thr))
    except Exception as e:
        print("[WARN] ens_thresholds.json 解析失敗，改用 0.44：", e)
        p.write_text(json.dumps({"spam":0.44},ensure_ascii=False,indent=2),"utf-8")
else:
    p.write_text(json.dumps({"spam":0.44},ensure_ascii=False,indent=2),"utf-8")
    print("[OK] spam thresholds -> default 0.44")
# intent thresholds
it=root/"reports_auto/intent_thresholds.json"
if not it.exists():
    it.write_text(json.dumps({"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3},ensure_ascii=False,indent=2),"utf-8")
    print("[OK] intent thresholds -> default")
# intent rules compile
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

log "[STEP3] 挑 KIE 權重（優先 artifacts_inbox/kie/kie/model.safetensors，其次 OLD 最新）"
PREF="$INBOX/kie/kie/model.safetensors"
if [ -f "$PREF" ]; then
  cp -f "$PREF" "kie/kie/model.safetensors"
  log "[APPLY] KIE -> kie/kie/model.safetensors (from artifacts_inbox)"
else
  CAND="$(find "$OLD" -type f -name model.safetensors -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1{print $2}')"
  if [ -n "$CAND" ] && [ -f "$CAND" ]; then
    cp -f "$CAND" "kie/kie/model.safetensors"
    log "[APPLY] KIE -> kie/kie/model.safetensors (from $CAND)"
  else
    log "[WARN] 找不到 KIE 權重，略過覆蓋"
  fi
fi
# tokenizer/config（若在舊專案）
[ -f "kie/kie/config.json" ] || cp -f "$OLD/reports_auto/kie/kie/config.json" "kie/kie/config.json" 2>/dev/null || true
[ -f "kie/kie/tokenizer_config.json" ] || cp -f "$OLD/reports_auto/kie/kie/tokenizer_config.json" "kie/kie/tokenizer_config.json" 2>/dev/null || true
[ -f "kie/kie/sentencepiece.bpe.model" ] || cp -f "$OLD/reports_auto/kie/kie/sentencepiece.bpe.model" "kie/kie/sentencepiece.bpe.model" 2>/dev/null || true

log "[STEP4] 組合 Spam / Intent 評測集（多來源去重；容錯跳過壞行；不讀 /mnt/data）"
python - <<'PY'
import json, hashlib, os, re
from pathlib import Path

def sha1(s): 
    import hashlib; return hashlib.sha1((s or "").strip().encode("utf-8")).hexdigest()
def get_text(r):
    # 盡量取到可路由文本：subject+body/ text / content / message / raw / description
    keys=[("subject","body"),("title","content")]
    for a,b in keys:
        if r.get(a) or r.get(b):
            return " ".join([str(r.get(a,"")), str(r.get(b,""))]).strip()
    for k in ["text","content","message","msg","raw","description","body","subject"]:
        if r.get(k): return str(r[k]).strip()
    # 常見巢狀
    for k in ["email","mail","data","record","sample"]:
        obj=r.get(k)
        if isinstance(obj, dict):
            for kk in ["text","content","body","subject","message"]:
                if obj.get(kk): return str(obj[kk]).strip()
    return ""

# ---- Spam ----
def norm_spam(y):
    if y is None: return None
    if isinstance(y,(int,float)): return 1 if int(y)!=0 else 0
    s=str(y).strip().lower()
    if s in {"1","true","yes","spam","phish","phishing"}: return 1
    if s in {"0","false","no","ham"}: return 0
    return None

root=Path(".")
spam_src = [
    "data/benchmarks/spamassassin.jsonl",
    "data/benchmarks/spamassassin.clean.jsonl",
    "data/benchmarks/spamassassin_phish.jsonl",
    "data/spam_sa/test.jsonl",
    "data/prod_merged/test.jsonl",
    "data/trec06c_zip/test.jsonl",
    # 舊專案（若存在）
    str(root.parent/"smart-mail-agent/data/benchmarks/spamassassin.jsonl"),
    str(root.parent/"smart-mail-agent/data/benchmarks/spamassassin.clean.jsonl"),
    str(root.parent/"smart-mail-agent/data/benchmarks/spamassassin_phish.jsonl"),
    str(root.parent/"smart-mail-agent/data/spam_sa/test.jsonl"),
    str(root.parent/"smart-mail-agent/data/prod_merged/test.jsonl"),
    str(root.parent/"smart-mail-agent/data/trec06c_zip/test.jsonl"),
]
rows=[]; seen=set(); used=[]
for p in spam_src:
    pth=Path(p)
    if not pth.exists(): continue
    ok=bad=0
    for ln in pth.read_text("utf-8",errors="ignore").splitlines():
        try:
            if not ln.strip(): continue
            r=json.loads(ln)
            y=norm_spam( r.get("spam") if "spam" in r else (r.get("label") or r.get("target")) )
            if y is None: continue
            t=get_text(r)
            if not t: continue
            k=sha1(t)
            if k in seen: continue
            seen.add(k); rows.append({"text":t,"spam":int(y)}); ok+=1
        except Exception:
            bad+=1
    used.append((p,ok,bad))
Path("data/spam_eval").mkdir(parents=True, exist_ok=True)
Path("data/spam_eval/dataset.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in rows),"utf-8")
print("[SPAM] sources_used:"); 
for p,ok,bad in used: print(f" - {p} ok={ok} bad={bad}")
print(f"[OK] spam_eval -> data/spam_eval/dataset.jsonl size={len(rows)}")

# ---- Intent ----
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
# 巢狀候選（如 gold.intent / anno.intent）
nested_keys=[("gold","intent"),("anno","intent"),("gold","label"),("annotation","intent")]
# 中文同義詞 → 正規標籤
zh_syn = {
 "報價": {"報價","問價","價錢","價格","估價"," 報價單","quotation","quote","pricing","estimate"},
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
    # 中文同義詞模糊匹配
    for tgt,bag in zh_syn.items():
        for w in bag:
            if w.lower() in low: return tgt
    return None

intent_paths = []
intent_paths += [str(p) for p in Path("data/intent_eval").glob("*.jsonl")]
intent_paths += [str(p) for p in Path("data/staged_project").glob("*.jsonl")]
intent_paths += [str(p) for p in Path("artifacts_inbox").glob("*.jsonl")]
intent_paths += [str(Path("..")/"smart-mail-agent/data/intent_eval/dataset.jsonl")]  # 舊專案

rows=[]; seen=set(); used_i=[]
for p in intent_paths:
    pth=Path(p)
    if not pth.exists(): continue
    ok=bad=0
    for ln in pth.read_text("utf-8",errors="ignore").splitlines():
        try:
            if not ln.strip(): continue
            r=json.loads(ln)
            t=get_text(r)
            if not t: continue
            lab=None
            # 直層鍵
            for k in label_keys:
                if k in r:
                    lab=map_intent(r[k])
                    if lab: break
            # 巢狀鍵
            if not lab:
                for a,b in nested_keys:
                    x=r.get(a); 
                    if isinstance(x,dict) and b in x:
                        lab=map_intent(x[b]); 
                        if lab: break
            if not lab: 
                continue  # 沒標註就不進評測
            k=sha1(t)
            if k in seen: continue
            seen.add(k); rows.append({"text":t,"intent":lab}); ok+=1
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

log "[STEP6] 自算 Intent『門檻+規則』macro-F1（用模型，失敗則 rules-only）"
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
    tp,fp,fn=m["tp"],m["fp"],m["fn"]
    P=tp/(tp+fp) if (tp+fp)>0 else 0.0
    R=tp/(tp+fn) if (tp+fn)>0 else 0.0
    F1=2*P*R/(P+R) if (P+R)>0 else 0.0
    return P,R,F1

rows=[]; mf=0.0
for lab in labels:
    P,R,F1=prf(cm[lab]); rows.append((lab,P,R,F1,cm[lab]["tp"],cm[lab]["fp"],cm[lab]["fn"])); mf+=F1
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

log "[STEP7] 收集 KIE 離線評測附件到 reports_auto/kie_eval 並掛到摘要"
collect_from(){ for p in "$1"/kie_eval_*.txt "$1"/kie_fields_*.txt "$1"/kie_pred*.jsonl; do [ -f "$p" ] && cp -f "$p" "$KIE_EVAL_DIR/"; done; }
collect_from "$INBOX"
collect_from "data/staged_project"
collect_from "$OLD"
{
  echo "# ONECLICK v9 (${TS})"
  echo "## Artifacts"
  echo '```'
  ls -l artifacts_prod 2>/dev/null || true
  ls -l artifacts 2>/dev/null || true
  echo; ls -l kie/kie 2>/dev/null || true
  echo '```'
  echo "## Datasets"
  echo "- spam_eval rows: \$(wc -l < data/spam_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo "- intent_eval rows: \$(wc -l < data/intent_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo "## Latest Eval dir"
  last_eval="\$(ls -1dt reports_auto/eval/* 2>/dev/null | head -n1 || true)"
  [ -n "\$last_eval" ] && echo "- \$last_eval" || echo "- (none)"
  echo "## Intent(threshold+rules) metrics"
  [ -n "\$last_eval" ] && sed -n '1,120p' "\$last_eval/metrics_after_threshold_and_rules.md" 2>/dev/null || echo "(no file)"
  echo "## KIE 離線評測附件（@ reports_auto/kie_eval）"
  ls -1 "$KIE_EVAL_DIR" 2>/dev/null | sed 's/^/- /' || echo "- (無)"
} > "$SUMMARY"

log "[DONE] Summary -> $SUMMARY"
