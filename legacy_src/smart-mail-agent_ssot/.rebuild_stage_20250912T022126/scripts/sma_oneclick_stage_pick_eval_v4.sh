#!/usr/bin/env bash
# 入倉 spam/intent（優先 artifacts_inbox，其次 /mnt/data）→ 只從 OLD 專案挑最新 KIE 權重
# → 組合評測集 → 跑 evaluator → 產出 Intent(門檻+規則) 指標 → 摘要 + 掛 KIE 附件
set -o pipefail

OLD="/home/youjie/projects/smart-mail-agent"
NEW="/home/youjie/projects/smart-mail-agent_ssot"
INBOX="$NEW/artifacts_inbox"
TS="$(date +%Y%m%dT%H%M%S)"
STATUS_DIR="$NEW/reports_auto/status"
ERR_DIR="$NEW/reports_auto/errors"
EVAL_DIR="$NEW/reports_auto/eval"
LOG="$ERR_DIR/ONECLICK_v4_${TS}.log"
SUMMARY="$STATUS_DIR/ONECLICK_v4_${TS}.md"

mkdir -p "$STATUS_DIR" "$ERR_DIR" \
         "$NEW/artifacts_prod" "$NEW/artifacts" "$NEW/kie/kie" \
         "$NEW/data/spam_eval" "$NEW/data/intent_eval" \
         "$NEW/src/smart_mail_agent/ml" "$NEW/configs" "$NEW/reports_auto/kie_eval"

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
stage_one(){ src="$1"; dst="$2"; [ -f "$src" ] && { cp -f "$src" "$dst"; log "  staged $(basename "$src") -> $dst"; } || true; }
try_stage(){
  local name="$1" dst="$2"
  stage_one "$INBOX/$name" "$dst"
  stage_one "/mnt/data/$name" "$dst"
}

# Spam
try_stage model_pipeline.pkl   artifacts_prod/model_pipeline.pkl
try_stage ens_thresholds.json  artifacts_prod/ens_thresholds.json
try_stage model_meta.json      artifacts_prod/model_meta.json
try_stage spam_rules.json      artifacts_prod/spam_rules.json

# Intent
try_stage intent_pro_cal.pkl        artifacts/intent_pro_cal.pkl
try_stage intent_pipeline_fixed.pkl artifacts/intent_pipeline_fixed.pkl
try_stage intent_clf.pkl            artifacts/intent_clf.pkl
try_stage intent_rules.json         configs/intent_rules.json

# 若 INBOX 有 77.zip，就解開補檔（不覆蓋既有同名檔）
if [ -f "$INBOX/77.zip" ]; then
  log "[STEP1b] 解 77.zip（只補缺檔）"
  TMP="$(mktemp -d)"; unzip -oq "$INBOX/77.zip" -d "$TMP"
  for f in model_pipeline.pkl ens_thresholds.json model_meta.json spam_rules.json; do
    [ -f "artifacts_prod/$f" ] || [ ! -f "$TMP/$f" ] || cp -n "$TMP/$f" "artifacts_prod/$f"
  done
  for f in intent_pro_cal.pkl intent_pipeline_fixed.pkl intent_clf.pkl; do
    [ -f "artifacts/$f" ] || [ ! -f "$TMP/$f" ] || cp -n "$TMP/$f" "artifacts/$f"
  done
  # KIE 設定檔（77.zip 裡只有設定，沒有權重）
  for f in config.json tokenizer_config.json sentencepiece.bpe.model; do
    [ -f "kie/kie/$f" ] || [ ! -f "$TMP/kie_xlmr.stub/$f" ] || cp -n "$TMP/kie_xlmr.stub/$f" "kie/kie/$f"
  done
  rm -rf "$TMP"
fi

log "[STEP2] 標準化門檻 + 編譯 intent 規則"
python - <<'PY'
import json, pathlib, re
root=pathlib.Path(".")
# spam thresholds
p=root/"artifacts_prod/ens_thresholds.json"
if p.exists():
    j=json.loads(p.read_text("utf-8"))
    thr = j.get("spam") if isinstance(j.get("spam"),(int,float)) else j.get("threshold",0.44)
    p.write_text(json.dumps({"spam": float(thr)},ensure_ascii=False,indent=2),"utf-8")
    print("[OK] spam thresholds ->", float(thr))
else:
    p.write_text(json.dumps({"spam":0.44},indent=2,ensure_ascii=False),"utf-8")
    print("[OK] spam thresholds -> default 0.44")

# intent thresholds（如果沒有就用常用預設）
it=root/"reports_auto/intent_thresholds.json"
if not it.exists():
    it.write_text(json.dumps({"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3},indent=2,ensure_ascii=False),"utf-8")
    print("[OK] intent thresholds -> default")

# 編譯 intent 規則：把 {labels, keywords:{label:[kw...]}} 轉成 {priority, patterns:{label: "(a|b|c)" }}
ir=root/"configs/intent_rules.json"
if ir.exists():
    j=json.loads(ir.read_text("utf-8"))
    kw=j.get("keywords") or {}
    rx={k:"("+"|".join(map(re.escape,(v or [])))+")" for k,v in kw.items()}
    out={"priority":["投訴","報價","技術支援","規則詢問","資料異動","其他"],"patterns":rx}
    (root/"configs/intent_rules_compiled.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
    print("[OK] intent rules -> configs/intent_rules_compiled.json")
else:
    print("[INFO] no intent_rules.json; will use built-ins when needed")
PY

log "[STEP3] 只從 OLD 專案挑最新 KIE 權重（mtime 最大的 model.safetensors）"
pick_kie(){
  local src
  src="$(find "$OLD" -type f -name model.safetensors -printf "%T@ %p\n" 2>/dev/null | sort -nr | awk 'NR==1{for(i=2;i<=NF;i++){printf (i>2?" ":""); printf $i};print ""}')"
  if [ -n "$src" ] && [ -f "$src" ]; then
    [ -f "kie/kie/model.safetensors" ] && cp -f "kie/kie/model.safetensors" "kie/kie/model.safetensors.bak_${TS}"
    cp -f "$src" "kie/kie/model.safetensors"
    log "[APPLY] KIE -> kie/kie/model.safetensors  (from: $src)"
    # 旁掛設定（若缺）
    for f in config.json tokenizer_config.json sentencepiece.bpe.model; do
      [ -f "kie/kie/$f" ] || { cand="$(dirname "$src")/$f"; [ -f "$cand" ] && cp -f "$cand" "kie/kie/$f"; }
    done
  else
    log "[WARN] 找不到 OLD 專案的 model.safetensors；KIE 評測會略過執行，只保留你上傳的離線評測附件"
  fi
}
pick_kie

log "[STEP4] 組合 spam / intent 評測集（去重；缺就略過）"
python - <<'PY'
import json, hashlib, re, pathlib
root=pathlib.Path(".")
# Spam：合併 /mnt/data 的三份 SA 檔案
def norm_spam(y):
    if y is None: return None
    s=str(y).lower()
    if s in {"1","true","yes","spam","phish","phishing"}: return 1
    if s in {"0","false","no","ham"}: return 0
    try: return int(float(s))
    except: return None
def text_of(r): return r.get("text") or r.get("body") or r.get("subject") or ""
rows=[]
for name in ["spamassassin.jsonl","spamassassin.clean.jsonl","spamassassin_phish.jsonl"]:
    p=pathlib.Path("/mnt/data")/name
    if not p.exists(): continue
    for ln in p.read_text("utf-8").splitlines():
        if not ln.strip(): continue
        try: r=json.loads(ln)
        except: continue
        y=r.get("spam", None); y = y if y is not None else r.get("label", None)
        y=norm_spam(y)
        if y is None: continue
        rows.append({"text": text_of(r), "spam": int(y)})
seen=set(); dedup=[]
for r in rows:
    k=hashlib.sha1(r["text"].strip().encode("utf-8")).hexdigest()
    if k in seen: continue
    seen.add(k); dedup.append(r)
(root/"data/spam_eval").mkdir(parents=True, exist_ok=True)
(root/"data/spam_eval/dataset.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in dedup),"utf-8")
print(f"[OK] spam_eval -> data/spam_eval/dataset.jsonl size={len(dedup)} spam={sum(1 for x in dedup if x['spam']==1)} ham={sum(1 for x in dedup if x['spam']==0)}")

# Intent：以 /mnt/data/test_labeled.jsonl 為主
rows=[]
p=pathlib.Path("/mnt/data/test_labeled.jsonl")
if p.exists():
    mp={"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
    for ln in p.read_text("utf-8").splitlines():
        if not ln.strip(): continue
        r=json.loads(ln)
        lab = r.get("intent") or r.get("label")
        lab = mp.get(lab, lab)
        txt = r.get("text") or r.get("body") or r.get("subject") or ""
        if not str(lab).strip(): continue
        rows.append({"text":txt,"intent":lab})
(root/"data/intent_eval").mkdir(parents=True, exist_ok=True)
(root/"data/intent_eval/dataset.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in rows),"utf-8")
print(f"[OK] intent_eval -> data/intent_eval/dataset.jsonl size={len(rows)}")
PY

log "[STEP5] 跑 evaluator（若腳本存在就跑）"
[ -x sma_oneclick_eval.sh ] && bash sma_oneclick_eval.sh data/spam_eval || log "[INFO] 無 sma_oneclick_eval.sh（spam），略過"
[ -x sma_oneclick_eval.sh ] && bash sma_oneclick_eval.sh data/intent_eval || log "[INFO] 無 sma_oneclick_eval.sh（intent），略過"

log "[STEP6] 另算 Intent『門檻+規則』macro-F1（如果最新 eval 有 eval_pred.jsonl）"
python - <<'PY'
import json, re, pathlib
root=pathlib.Path(".")
eval_dirs=sorted([p for p in (root/"reports_auto/eval").glob("*") if (p/"eval_pred.jsonl").exists()], key=lambda p:p.stat().st_mtime)
if not eval_dirs:
    print("[WARN] 沒有 eval_pred.jsonl，跳過 rules+threshold 指標"); raise SystemExit(0)
E=eval_dirs[-1]
def load_jsonl(p): return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
ds=load_jsonl(E/"eval_ds.jsonl"); pr=load_jsonl(E/"eval_pred.jsonl")
n=min(len(ds),len(pr)); ds,pr=ds[:n],pr[:n]
th=json.loads((root/"reports_auto/intent_thresholds.json").read_text("utf-8"))
# 規則：優先用你提供的 compiled；否則內建
RX={}
cp=root/"configs/intent_rules_compiled.json"
if cp.exists():
    j=json.loads(cp.read_text("utf-8")); RX={k:re.compile(v,re.I) for k,v in (j.get("patterns") or {}).items()}
else:
    pat={
        "投訴": r"(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)",
        "報價": r"(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)",
        "技術支援": r"(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)",
        "規則詢問": r"(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)",
        "資料異動": r"(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)",
    }
    RX={k:re.compile(v,re.I) for k,v in pat.items()}
priority=["投訴","報價","技術支援","規則詢問","資料異動"]
def rule_pick(text):
    for lab in priority:
        rx=RX.get(lab)
        if rx and rx.search(text or ""): return lab
    return None
cm={}
labels=set([d.get("intent") for d in ds if d.get("intent")]); labels |= set(th.keys()); labels |= set(RX.keys())
for lab in labels: cm[lab]={"tp":0,"fp":0,"fn":0}
for d,p in zip(ds,pr):
    gold=d.get("intent")
    text=d.get("text") or d.get("body") or d.get("subject") or ""
    pred=p.get("pred_intent"); conf=float(p.get("intent_conf") or 0.0)
    thr=th.get(pred, th.get("其他",0.4))
    routed=pred
    if conf < thr:
        routed=rule_pick(text) or "其他"
    else:
        r=rule_pick(text)
        if r and r!=pred: routed=r
    if routed==gold: cm[gold]["tp"]+=1
    else: cm[routed]["fp"]+=1; cm[gold]["fn"]+=1
def f1(tp,fp,fn):
    p= tp/(tp+fp) if (tp+fp)>0 else 0.0
    r= tp/(tp+fn) if (tp+fn)>0 else 0.0
    return (2*p*r/(p+r)) if (p+r)>0 else 0.0, p, r
rows=[]; mf=0.0
for lab in sorted(labels):
    tp,fp,fn=cm[lab]["tp"],cm[lab]["fp"],cm[lab]["fn"]
    F,P,R=f1(tp,fp,fn); mf+=F; rows.append((lab,P,R,F,tp,fp,fn))
mf=mf/len(labels) if labels else 0.0
md=["# Intent metrics (threshold + rules)", f"- macro_f1_after_threshold_and_rules: {mf:.3f}","","|label|P|R|F1|TP|FP|FN|","|---|---:|---:|---:|---:|---:|---:|"]
for lab,P,R,F,TP,FP,FN in rows: md.append(f"|{lab}|{P:.3f}|{R:.3f}|{F:.3f}|{TP}|{FP}|{FN}|")
(E/"metrics_after_threshold_and_rules.md").write_text("\n".join(md),"utf-8")
print("[OK] wrote", E/"metrics_after_threshold_and_rules.md")
PY

log "[STEP7] 收集 KIE 離線評測附件到 reports_auto/kie_eval 並掛到摘要"
for f in /mnt/data/kie_eval_*.txt /mnt/data/kie_fields_*.txt /mnt/data/kie_pred*.jsonl; do
  [ -f "$f" ] && cp -f "$f" "$NEW/reports_auto/kie_eval/" || true
done

# 摘要
{
  echo "# ONECLICK v4 ($TS)"
  echo "- OLD: $OLD"
  echo "- INBOX: $INBOX"
  echo
  echo "## Datasets"
  echo "- spam_eval rows: $(wc -l < data/spam_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo "- intent_eval rows: $(wc -l < data/intent_eval/dataset.jsonl 2>/dev/null || echo 0)"
  echo
  last_eval="$(ls -1dt "$EVAL_DIR"/* 2>/dev/null | head -n1 || true)"
  if [ -n "$last_eval" ]; then
    echo "## Latest Eval: $last_eval"
    sed -n '1,80p' "$last_eval/metrics.md" 2>/dev/null || true
    echo "---- Intent(threshold+rules) ----"
    sed -n '1,160p' "$last_eval/metrics_after_threshold_and_rules.md" 2>/dev/null || true
  fi
  echo
  echo "## KIE 離線評測附件（@ reports_auto/kie_eval）"
  if ls -1 reports_auto/kie_eval/* >/dev/null 2>&1; then
    ls -1 reports_auto/kie_eval/* | sed 's/^/- /'
  else
    echo "- (無附檔)"
  fi
} > "$SUMMARY"

log "[DONE] Summary -> $SUMMARY"
