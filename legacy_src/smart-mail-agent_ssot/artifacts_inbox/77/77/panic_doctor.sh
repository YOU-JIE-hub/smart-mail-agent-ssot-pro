#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
umask 022
PS4='+ [${BASH_SOURCE##*/}:${LINENO}] ► '
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] 無法進入專案：$ROOT"; exit 96; }
LOG_DIR="$ROOT/.sma_logs"; mkdir -p "$LOG_DIR"; TS="$(date +%Y-%m-%d_%H%M%S)"; LOG="$LOG_DIR/panic_${TS}.log"
exec > >(tee -a "$LOG") 2>&1
echo "[ENV] $(command -v python3 >/dev/null && python3 -V || python -V 2>/dev/null || echo 'python N/A')"

# --- 函式 ---
run_step() {
  local name="$1"; shift
  local out="$LOG_DIR/${TS}_${name// /_}.out"; local err="$LOG_DIR/${TS}_${name// /_}.err"
  echo ""; echo "========== [STEP] $name =========="
  set +e; { "$@"; } > >(tee -a "$out") 2> >(tee -a "$err" >&2); rc=$?; set -e
  if [ $rc -ne 0 ]; then
    echo "---------- [FAIL] $name rc=$rc ----------"
    echo "[stderr 末 60 行]"; tail -n 60 "$err" || true
    echo "[stdout 末 40 行]"; tail -n 40 "$out" || true
    echo "[LOG] 全部日誌：$LOG"
    exit $rc
  fi
  echo "---------- [OK] $name ----------"
}

# --- 0) 啟用 .venv（若有） ---
if [ -f ".venv/bin/activate" ]; then source ".venv/bin/activate"; echo "[ENV] .venv 啟用：$(python -V 2>&1)"; fi
PY="$(command -v python3 || command -v python || true)"; : "${PY:?找不到 python}"

# --- 1) 若缺資料就自動合成（一次到位：train/val/test + KIE gold）---
if [ ! -s "data/intent/train.jsonl" ] || [ ! -s "data/intent/val.jsonl" ] || [ ! -s "data/intent/test.jsonl" ]; then
  echo "[INFO] 偵測到缺少資料，產生合成資料以救援"
  if [ ! -s "sma_tools/generate_mail_dataset.py" ]; then
    cat > sma_tools/generate_mail_dataset.py <<'PY'
#!/usr/bin/env python3
import json,random,argparse,os,re
from pathlib import Path
R=random.Random(42)
INTENTS=["biz_quote","complaint","other","policy_qa","profile_update","tech_support"]
ENVS=["prod","production","staging","test","dev"]; CUR=["NT$","USD","$"]
def r_amt(): return f"{random.choice(CUR)}{R.randint(100,50000):,}"
def r_date():
  if R.random()<0.6: y=R.choice([2024,2025]); m=R.randint(1,12); d=R.randint(1,28); return f"{y}/{m:02d}/{d:02d}"
  m=R.randint(1,12); d=R.randint(1,28); return f"{m}/{d}"
def mk(it):
  a=r_amt(); d=r_date(); e=R.choice(ENVS)
  if it=="biz_quote": s=f"請問 {d} 前能提供報價？{R.randint(5,80)} 位，約 {a}。"
  elif it=="complaint": s=f"我們對上次服務不滿，{d} 已寄出投訴表，請回覆。"
  elif it=="policy_qa": s="想了解 API 使用政策與資安規範，有沒有文件與 SLA 說明？"
  elif it=="profile_update": s="請協助更新公司聯絡資訊與發票抬頭，本周內完成即可。"
  elif it=="tech_support": s=f"{e} 無法登入，{d} 仍持續，錯誤碼 401，請協助。"
  else: s="想索取產品簡介與 SDK 下載連結，謝謝。"
  return {"text": s, "label": it}
def split(n): return n//6
def build(n,fn): out=[]; per=split(n); 
  [out.extend(mk(it) for _ in range(per)) for it in INTENTS]; R.shuffle(out); Path(fn).parent.mkdir(parents=True,exist_ok=True); open(fn,"w",encoding="utf-8").write("\n".join(json.dumps(x,ensure_ascii=False) for x in out))
def kie_gold(src, fn, maxn=120):
  import re; rows=[json.loads(l) for l in open(src,encoding="utf-8")]
  out=[]
  for r in rows[:maxn]:
    t=r["text"]; spans=[]
    m=re.search(r"\d{4}/\d{2}/\d{2}",t) or re.search(r"\d{1,2}/\d{1,2}",t)
    if m: spans.append({"start":m.start(),"end":m.end(),"label":"date_time"})
    for cur in CUR:
      i=t.find(cur)
      if i!=-1:
        j=i+len(cur)
        while j<len(t) and (t[j].isdigit() or t[j] in ",."): j+=1
        spans.append({"start":i,"end":j,"label":"amount"}); break
    for e in ENVS:
      i=t.lower().find(e)
      if i!=-1: spans.append({"start":i,"end":i+len(e),"label":"env"}); break
    out.append({"text":t,"spans":spans})
  Path(fn).parent.mkdir(parents=True,exist_ok=True)
  open(fn,"w",encoding="utf-8").write("\n".join(json.dumps(x,ensure_ascii=False) for x in out))
if __name__=="__main__":
  build(1200,"data/intent/train.jsonl"); build(300,"data/intent/val.jsonl"); build(300,"data/intent/test.jsonl"); kie_gold("data/intent/test.jsonl","data/kie/test.jsonl")
PY
    chmod +x sma_tools/generate_mail_dataset.py
  fi
  run_step "產生合成資料" "$PY" sma_tools/generate_mail_dataset.py
else
  echo "[OK] 已偵測到資料：data/intent/{train,val,test}.jsonl"
fi

# --- 2) 依賴健檢 ---
run_step "依賴健檢" "$PY" - <<'PY'
import importlib,sys
mods=["yaml","torch","transformers","seqeval","sklearn"]
miss=[m for m in mods if importlib.util.find_spec(m) is None]
print("[DEPS] missing:", ",".join(miss) if miss else "<none>")
PY

# --- 3) Intent：如有守護腳本就用，沒有就 inline 訓練 ---
if [ -x "sma_tools/sma_guarded_intent.sh" ]; then
  run_step "Intent 訓練(guarded)" sma_tools/sma_guarded_intent.sh
else
  run_step "Intent 訓練(內建)" "$PY" - <<'PY'
import json,joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report,confusion_matrix,accuracy_score
def L(p): return [json.loads(l) for l in open(p,encoding="utf-8")]
tr=L("data/intent/train.jsonl"); va=L("data/intent/val.jsonl"); te=L("data/intent/test.jsonl")
Xtr=[o["text"] for o in tr]; ytr=[o["label"] for o in tr]
Xva=[o["text"] for o in va]; yva=[o["label"] for o in va]
Xte=[o["text"] for o in te]; yte=[o["label"] for o in te]
base=Pipeline([("tfidf",TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=100000)),("clf",LinearSVC())])
cal=CalibratedClassifierCV(estimator=base,method="sigmoid",cv=3).fit(Xtr,ytr)
def E(n,X,y):
  yp=cal.predict(X); acc=accuracy_score(y,yp)
  Path("reports_auto",f"intent_{n}_report.txt").write_text(classification_report(y,yp,digits=4),encoding="utf-8")
  print(f"[{n}] acc={acc:.4f}")
E("val",Xva,yva); E("test",Xte,yte)
Path("artifacts").mkdir(exist_ok=True); joblib.dump(cal,"artifacts/intent_pro_cal.pkl"); print("[MODEL] artifacts/intent_pro_cal.pkl")
PY
fi

# --- 4) KIE：如有守護腳本就用，否則逐步跑 ---
[ -s ".sma_tools/ruleset.yml" ] || cat > .sma_tools/ruleset.yml <<'YAML'
labels: [amount, date_time, env]
patterns:
  amount: ["(?:NT\\$|USD|\\$)\\s?\\d[\\d,]*(?:\\.\\d+)?"]
  date_time: ["(\\d{4}[/-]\\d{1,2}[/-]\\d{1,2})","(\\d{1,2}/\\d{1,2})"]
  env: ["\\b(prod|production|staging|stage|test|dev)\\b"]
YAML
if [ -x "sma_tools/sma_guarded_kie.sh" ]; then
  run_step "KIE 一鍵(guarded)" sma_tools/sma_guarded_kie.sh --in-jsonl data/intent/train.jsonl --eval-gold data/kie/test.jsonl --epochs 3 --seed 42
else
  # 沒有守護腳本就直接呼叫 .sma_tools/*；如缺則報錯並印提示
  for f in .sma_tools/generate_silver_kie.py .sma_tools/train_kie.py .sma_tools/inference_kie.py .sma_tools/eval_kie.py; do
    [ -s "$f" ] || { echo "[FATAL] 缺少 $f，請讓我補寫或先執行我之前提供的建立指令"; exit 97; }
  done
  run_step "KIE 銀標"    "$PY" .sma_tools/generate_silver_kie.py --in_jsonl data/intent/train.jsonl --out_jsonl data/kie/silver.jsonl --rules .sma_tools/ruleset.yml
  run_step "KIE 訓練"    "$PY" .sma_tools/train_kie.py --silver data/kie/silver.jsonl --model_dir artifacts/kie_xlmr --base_model xlm-roberta-base --epochs 3 --seed 42 --max_len 512
  run_step "KIE 推論"    "$PY" .sma_tools/inference_kie.py --model_dir artifacts/kie_xlmr --in_jsonl data/intent/train.jsonl --out_jsonl reports_auto/kie_pred.jsonl --max_len 512
  [ -s data/kie/test.jsonl ] && run_step "KIE 評測" "$PY" .sma_tools/eval_kie.py --pred reports_auto/kie_pred.jsonl --gold data/kie/test.jsonl --model_dir artifacts/kie_xlmr --out reports_auto/kie_eval.txt --max_len 512 || echo "[INFO] 無 gold，略過評測"
fi

echo "========== [RESULTS] =========="
ls -l artifacts/intent_pro_cal.pkl 2>/dev/null || true
ls -l artifacts/kie_xlmr 2>/dev/null || true
head -n 2 reports_auto/kie_pred.jsonl 2>/dev/null || true
[ -s reports_auto/kie_eval.txt ] && cat reports_auto/kie_eval.txt || echo "[INFO] 尚無 KIE 評測"
echo "[LOG] 完整日誌：$LOG"
