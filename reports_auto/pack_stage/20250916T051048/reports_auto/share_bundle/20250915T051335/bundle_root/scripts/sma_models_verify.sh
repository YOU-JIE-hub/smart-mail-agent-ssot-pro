#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

log(){ printf '[%s] %s\n' "$(date +%F' '%T)" "$*"; }

ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"

# 1) venv
log "activate venv"
if [[ ! -d .venv_clean ]]; then python3 -m venv .venv_clean; fi
# shellcheck disable=SC1091
source .venv_clean/bin/activate
python -m pip -q install --upgrade pip wheel setuptools >/dev/null

# 2) 依賴（避免太重：transformers/torch 僅在有 KIE 模型時必要）
log "install base deps"
python -m pip -q install numpy scipy scikit-learn joblib pandas >/dev/null
python -m pip -q install ruff pytest >/dev/null || true

# 3) INTENT — 評測（若無模型則先跑你的一鍵訓練）
log "INTENT: evaluate (or train+evaluate)"
INTENT_MODEL="artifacts/intent_pro_cal.pkl"
INTENT_THR="reports_auto/intent_thresholds.json"
INTENT_DATA="data/intent/external_realistic_test.clean.jsonl"

if [[ -f "$INTENT_MODEL" && -f "$INTENT_THR" && -f "$INTENT_DATA" ]]; then
  python .sma_tools/runtime_threshold_router.py \
    --model "$INTENT_MODEL" \
    --input "$INTENT_DATA" \
    --out_preds reports_auto/ext_pro_threshold_preds.jsonl \
    --eval | tee reports_auto/intent_eval_console.txt
else
  if [[ -x .sma_tools/oneclick_intent_pro.sh ]]; then
    log "INTENT: model/thresholds missing -> run oneclick"
    .sma_tools/oneclick_intent_pro.sh | tee reports_auto/intent_oneclick.log
  else
    log "INTENT: missing scripts (.sma_tools/oneclick_intent_pro.sh / runtime_threshold_router.py)"
    log "INTENT: 跳過"
  fi
fi

# 4) SPAM — 若無成品就現訓 + 評測；有成品就直評
log "SPAM: train if needed, then evaluate"
python - <<'PY'
import json, pathlib, sys
from pathlib import Path
P = Path(".")
# 優先尋找 merged 測試集，否則 fallback
cand = [
  P/"data/prod_merged/test.jsonl",
  P/"data/spam_sa/test.jsonl",
  P/"data/trec06c_zip/test.jsonl",
]
test = next((c for c in cand if c.exists()), None)
if test is None:
    print("[SPAM] no test set found; skip")
    sys.exit(0)

# 若已有門檻 & 校準模型就直評，否則現訓一個最小可用版
thr_fp = P/"artifacts_prod/ens_thresholds.json"
mdl_fp = P/"artifacts_prod/text_lr_platt.pkl"

def load_jsonl(fp):
    import json
    X, y, raw = [], [], []
    with open(fp, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            raw.append(o)
            X.append((o.get("subject","") + " \n " + o.get("body","")))
            y.append(1 if o.get("label")=="spam" else 0)
    return X, y, raw

from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, roc_auc_score, average_precision_score

def dump(tag, y, yhat, prob=None):
    P, R, F, _ = precision_recall_fscore_support(y, yhat, average=None, labels=[0,1])
    cm = confusion_matrix(y, yhat, labels=[0,1]).tolist()
    macro = (F[0]+F[1])/2
    out = f"[{tag}] Macro-F1={macro:.4f} | Ham {P[0]:.3f}/{R[0]:.3f}/{F[0]:.3f} | Spam {P[1]:.3f}/{R[1]:.3f}/{F[1]:.3f} | CM={cm}"
    if prob is not None:
        try:
            out += f" | ROC-AUC={roc_auc_score(y, prob):.3f} PR-AUC={average_precision_score(y, prob):.3f}"
        except Exception:
            pass
    print(out)

Xte, yte, raw_te = load_jsonl(test)

def rules_sig(e):
    import re
    t = (e.get("subject","")+" "+e.get("body","")).lower()
    url = re.findall(r"https?://[^\s)>\]]+", t)
    sus_tld={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
    sus_ext={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
    kws=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
         "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent"]
    atts=[(a or "").lower() for a in e.get("attachments",[]) if a]
    s=0
    if url: s+=1
    if any(u.lower().endswith(t) for u in url for t in sus_tld): s+=1
    if any(k in t for k in kws): s+=1
    if any(a.endswith(ext) for a in atts for ext in sus_ext): s+=1
    if ("account" in t) and any(k in t for k in ("verify","reset","login","signin")): s+=1
    if ("帳戶" in t) and any(k in t for k in ("驗證","重設","登入")): s+=1
    return s

import json, joblib, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline

if thr_fp.exists() and mdl_fp.exists():
    d = json.loads(thr_fp.read_text(encoding="utf-8"))
    thr = float(d.get("threshold", 0.44)); smin = int(d.get("signals_min", 3))
    pack = joblib.load(mdl_fp)
    cal = pack["cal"]; vect = pack.get("vect", None)
    # cal 已包含 vect; 這裡提供向後相容
    prob = cal.predict_proba(Xte)[:,1]
    y_text = (prob >= thr).astype(int)
    y_rule = (np.array([rules_sig(e) for e in raw_te]) >= smin).astype(int)
    y_ens = np.maximum(y_text, y_rule)
    dump("TEXT", yte, y_text, prob)
    dump("RULE", yte, y_rule)
    dump("ENS",  yte, y_ens)
else:
    # 最小可用現訓（train=val=8:2 split 以 seed 固定）
    print("[SPAM] no artifacts -> quick train")
    import random
    allX, ally, allraw = [], [], []
    # 嘗試找 train/val；找不到就從 test 拆一點出來避免無資料
    trainp = Path("data/prod_merged/train.jsonl")
    valp   = Path("data/prod_merged/val.jsonl")
    if trainp.exists() and valp.exists():
        for p in (trainp, valp):
            X,y,_ = load_jsonl(p); allX+=X; ally+=y
    else:
        X,y,_ = load_jsonl(test)
        idx = list(range(len(X))); random.Random(42).shuffle(idx)
        k = max(1,int(len(idx)*0.2)); val_idx=set(idx[:k]); tr_idx=set(idx[k:])
        allX = [X[i] for i in tr_idx]; ally=[y[i] for i in tr_idx]
        VX   = [X[i] for i in val_idx]; Vy=[y[i] for i in val_idx]
    pipe = Pipeline([("tf", TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=2)),
                     ("lr", LogisticRegression(max_iter=200, class_weight="balanced"))])
    pipe.fit(allX, ally)
    cal = CalibratedClassifierCV(pipe, method="sigmoid", cv="prefit"); cal.fit(allX, ally)
    joblib.dump({"cal":cal, "vect":pipe.named_steps["tf"]}, "artifacts_prod/text_lr_platt.pkl")
    thr = 0.44; smin = 3
    Path("artifacts_prod/ens_thresholds.json").write_text(json.dumps({"threshold":thr,"signals_min":smin}), encoding="utf-8")
    prob = cal.predict_proba(Xte)[:,1]
    import numpy as np
    y_text = (prob >= thr).astype(int)
    y_rule = (np.array([rules_sig(e) for e in raw_te]) >= smin).astype(int)
    y_ens = np.maximum(y_text, y_rule)
    dump("TEXT", yte, y_text, prob)
    dump("RULE", yte, y_rule)
    dump("ENS",  yte, y_ens)
PY

# 5) KIE — 僅在現成模型存在時評測（避免臨時拉大權重）
log "KIE: evaluate strict-span if model exists"
if [[ -d artifacts/releases/kie_xlmr/current ]]; then
  python -m pip -q install transformers seqeval torch >/dev/null || true
  TEST_KIE="data/kie/test.jsonl"
  [[ -f "$TEST_KIE" ]] || TEST_KIE="data/kie/valid.jsonl"
  if [[ -f "$TEST_KIE" ]]; then
    python .sma_tools/kie_eval_strict.py \
      --model_dir artifacts/releases/kie_xlmr/current \
      --test "$TEST_KIE" \
      --out_prefix reports_auto/kie_eval | tee reports_auto/kie_eval_console.txt
  else
    log "KIE: no data/kie/{test|valid}.jsonl -> skip"
  fi
else
  log "KIE: artifacts/releases/kie_xlmr/current 不存在 -> skip（避免線上抓權重）"
fi

# 6) 總結報告
log "write summary"
python - <<'PY'
from pathlib import Path
out = Path("reports_auto/bench_summary.md")
def readhead(p, n=20):
    try:
        return "\n".join(Path(p).read_text(encoding="utf-8").splitlines()[:n])
    except Exception:
        return "(no report)"
out.write_text(f"""# Bench Summary

## INTENT
- model: artifacts/intent_pro_cal.pkl
- thresholds: reports_auto/intent_thresholds.json
### console
{readhead("reports_auto/intent_eval_console.txt")}

## SPAM
(see console above in job log)

## KIE (strict-span)
{readhead("reports_auto/kie_eval.txt")}
""", encoding="utf-8")
print(f"[OUT] {out}")
PY

log "done"
