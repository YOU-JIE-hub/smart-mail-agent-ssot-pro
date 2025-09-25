#!/usr/bin/env bash
# 入倉 spam/intent → KIE 權重優先 artifacts_inbox/kie/kie/model.safetensors → 組評測集（多來源去重）
# → 跑 eval → Intent(門檻+規則) → 掛 KIE 附件 → 摘要
set -o pipefail
OLD="/home/youjie/projects/smart-mail-agent"
NEW="/home/youjie/projects/smart-mail-agent_ssot"
INBOX="$NEW/artifacts_inbox"
TS="$(date +%Y%m%dT%H%M%S)"
STATUS_DIR="$NEW/reports_auto/status"
ERR_DIR="$NEW/reports_auto/errors"
EVAL_DIR="$NEW/reports_auto/eval"
LOG="$ERR_DIR/ONECLICK_v5_${TS}.log"
SUMMARY="$STATUS_DIR/ONECLICK_v5_${TS}.md"

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
  # KIE 設定檔 stub
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
# intent thresholds default
it=root/"reports_auto/intent_thresholds.json"
if not it.exists():
    it.write_text(json.dumps({"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3},indent=2,ensure_ascii=False),"utf-8")
    print("[OK] intent thresholds -> default")
# 編譯 intent 規則 keywords -> regex
ir=root/"configs/intent_rules.json"
if ir.exists():
    j=json.loads(ir.read_text("utf-8")); kw=j.get("keywords") or {}
    rx={k:"("+"|".join(map(re.escape,(v or [])))+")" for k,v in kw.items()}
    (root/"configs/intent_rules_compiled.json").write_text(json.dumps({"priority":["投訴","報價","技術支援","規則詢問","資料異動","其他"],"patterns":rx},ensure_ascii=False,indent=2),"utf-8")
    print("[OK] intent rules -> configs/intent_rules_compiled.json")
else:
    print("[INFO] no intent_rules.json; will use built-ins if needed")
PY

log "[STEP3] 挑 KIE 權重（優先 artifacts_inbox/kie/kie/model.safetensors，其次 OLD 最新）"
pick_kie(){
  local prim="$INBOX/kie/kie/model.safetensors"
  if [ -f "$prim" ]; then
    [ -f "kie/kie/model.safetensors" ] && cp -f "kie/kie/model.safetensors" "kie/kie/model.safetensors.bak_${TS}"
    cp -f "$prim" "kie/kie/model.safetensors"
    log "[APPLY] KIE -> kie/kie/model.safetensors (from artifacts_inbox)"
    for f in config.json tokenizer_config.json sentencepiece.bpe.model; do
      [ -f "kie/kie/$f" ] || { cand="$INBOX/kie/kie/$f"; [ -f "$cand" ] && cp -f "$cand" "kie/kie/$f"; }
    done
    return
  fi
  # fallback: OLD mtime 最新
  local src
  src="$(find "$OLD" -type f -name model.safetensors -printf "%T@ %p\n" 2>/dev/null | sort -nr | awk 'NR==1{for(i=2;i<=NF;i++){printf (i>2?" ":""); printf $i};print ""}')"
  if [ -n "$src" ] && [ -f "$src" ]; then
    [ -f "kie/kie/model.safetensors" ] && cp -f "kie/kie/model.safetensors" "kie/kie/model.safetensors.bak_${TS}"
    cp -f "$src" "kie/kie/model.safetensors"
    log "[APPLY] KIE -> kie/kie/model.safetensors  (from: $src)"
    for f in config.json tokenizer_config.json sentencepiece.bpe.model; do
      [ -f "kie/kie/$f" ] || { cand="$(dirname "$src")/$f"; [ -f "$cand" ] && cp -f "$cand" "kie/kie/$f"; }
    done
  else
    log "[WARN] 找不到 KIE 權重；評測僅掛離線附件"
  fi
}
pick_kie

log "[STEP4] 組合 Spam / Intent 評測集（多來源去重；先用現有 data/*，再 /mnt/data，最後舊專案）"
python - <<'PY'
import json, hashlib, pathlib
root=pathlib.Path(".")

def sha(s): return __import__("hashlib").sha1((s or "").strip().encode("utf-8")).hexdigest()
def spam_norm(y):
    if y is None: return None
    s=str(y).lower()
    if s in {"1","true","yes","spam","phish","phishing"}: return 1
    if s in {"0","false","no","ham"}: return 0
    try: return int(float(s))
    except: return None
def text_of(r): return r.get("text") or r.get("body") or r.get("subject") or ""

# -------- Spam dataset --------
spam_out = root/"data/spam_eval/dataset.jsonl"
if not spam_out.exists() or spam_out.stat().st_size==0:
    candidates = [
        # 現有
        root/"data/benchmarks/spamassassin.jsonl",
        root/"data/benchmarks/spamassassin.clean.jsonl",
        root/"data/benchmarks/spamassassin_phish.jsonl",
        # /mnt/data
        pathlib.Path("/mnt/data/spamassassin.jsonl"),
        pathlib.Path("/mnt/data/spamassassin.clean.jsonl"),
        pathlib.Path("/mnt/data/spamassassin_phish.jsonl"),
        # 舊專案
        pathlib.Path("/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl"),
        pathlib.Path("/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.clean.jsonl"),
        pathlib.Path("/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin_phish.jsonl"),
        pathlib.Path("/home/youjie/projects/smart-mail-agent/data/spam_sa/test.jsonl"),
        pathlib.Path("/home/youjie/projects/smart-mail-agent/data/prod_merged/test.jsonl"),
        pathlib.Path("/home/youjie/projects/smart-mail-agent/data/trec06c_zip/test.jsonl"),
    ]
    rows=[]
    for p in candidates:
        try:
            for ln in p.read_text("utf-8").splitlines():
                if not ln.strip(): continue
                r=json.loads(ln)
                y = spam_norm(r.get("spam", r.get("label")))
                if y is None: continue
                rows.append({"text":text_of(r),"spam":int(y)})
        except FileNotFoundError:
            pass
    seen=set(); dedup=[]
    for r in rows:
        k=sha(r["text"])
        if k in seen: continue
        seen.add(k); dedup.append(r)
    spam_out.parent.mkdir(parents=True,exist_ok=True)
    spam_out.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in dedup),"utf-8")
    print(f"[OK] spam_eval -> {spam_out} size={len(dedup)}")
else:
    print(f"[OK] reuse {spam_out} size={sum(1 for _ in spam_out.open())}")

# -------- Intent dataset --------
intent_out = root/"data/intent_eval/dataset.jsonl"
if not intent_out.exists() or intent_out.stat().st_size==0:
    rows=[]
    # /mnt/data 的標準金標
    for p in [pathlib.Path("/mnt/data/test_labeled.jsonl")]:
        if p.exists():
            mp={"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
            for ln in p.read_text("utf-8").splitlines():
                if not ln.strip(): continue
                r=json.loads(ln)
                lab=r.get("intent") or r.get("label"); lab=mp.get(lab, lab)
                txt=r.get("text") or r.get("body") or r.get("subject") or ""
                if lab: rows.append({"text":txt,"intent":lab})
    # 舊專案的已整理評測集
    p_old = pathlib.Path("/home/youjie/projects/smart-mail-agent/data/intent_eval/dataset.jsonl")
    if p_old.exists() and not rows:
        rows = [json.loads(x) for x in p_old.read_text("utf-8").splitlines() if x.strip()]
    intent_out.parent.mkdir(parents=True,exist_ok=True)
    intent_out.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in rows),"utf-8")
    print(f"[OK] intent_eval -> {intent_out} size={len(rows)}")
else:
    print(f"[OK] reuse {intent_out} size={sum(1 for _ in intent_out.open())}")
PY

log "[STEP5] 跑 evaluator（若腳本存在且資料非空）"
SPAM_N=$(wc -l < data/spam_eval/dataset.jsonl 2>/dev/null || echo 0)
INT_N=$(wc -l < data/intent_eval/dataset.jsonl 2>/dev/null || echo 0)
if [ -x sma_oneclick_eval.sh ] && [ "$SPAM_N" -gt 0 ]; then bash sma_oneclick_eval.sh data/spam_eval; else log "[INFO] 略過 spam eval（無資料或無腳本）"; fi
if [ -x sma_oneclick_eval.sh ] && [ "$INT_N" -gt 0 ]; then bash sma_oneclick_eval.sh data/intent_eval; else log "[INFO] 略過 intent eval（無資料或無腳本）"; fi

log "[STEP6] Intent『門檻+規則』macro-F1（若最新 eval 有 eval_pred.jsonl）"
python - <<'PY'
import json, re, pathlib, sys
root=pathlib.Path(".")
eval_dirs=sorted([p for p in (root/"reports_auto/eval").glob("*") if (p/"eval_pred.jsonl").exists()], key=lambda p:p.stat().st_mtime)
if not eval_dirs:
    print("[INFO] 無 eval_pred.jsonl，跳過 rules+threshold 指標"); sys.exit(0)
E=eval_dirs[-1]
def load_jsonl(p): return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
ds=load_jsonl(E/"eval_ds.jsonl"); pr=load_jsonl(E/"eval_pred.jsonl")
n=min(len(ds),len(pr)); ds,pr=ds[:n],pr[:n]
th=json.loads((root/"reports_auto/intent_thresholds.json").read_text("utf-8"))
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
for base in "/mnt/data" "$INBOX" "$OLD"; do
  for f in "$base"/kie_eval_*.txt "$base"/kie_fields_*.txt "$base"/kie_pred*.jsonl; do
    [ -f "$f" ] && cp -f "$f" "$NEW/reports_auto/kie_eval/" || true
  done
done

# 摘要
{
  echo "# ONECLICK v5 ($TS)"
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
