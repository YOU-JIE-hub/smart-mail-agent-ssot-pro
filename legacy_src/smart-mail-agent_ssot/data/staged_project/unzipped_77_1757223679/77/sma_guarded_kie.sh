#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
umask 022
IFS=$'\n\t'
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] 無法進入專案：$ROOT"; exit 96; }
LOG_DIR="$ROOT/.sma_logs"; mkdir -p "$LOG_DIR"
TS="$(date +%Y-%m-%d_%H%M%S)"; LOG="$LOG_DIR/kie_guarded_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

# 參數（無 demo；必須提供實際資料）
IN=""; SILV="data/kie/silver.jsonl"; MD="artifacts/kie_xlmr"; PRED="reports_auto/kie_pred.jsonl"; GOLD=""
EPOCHS=3; SEED=42; BASE="xlm-roberta-base"; MAXLEN=512
while [ $# -gt 0 ]; do
  case "$1" in
    --in-jsonl) IN="$2"; shift 2;;
    --silver)   SILV="$2"; shift 2;;
    --model-dir)MD="$2"; shift 2;;
    --pred)     PRED="$2"; shift 2;;
    --eval-gold)GOLD="$2"; shift 2;;
    --epochs)   EPOCHS="$2"; shift 2;;
    --seed)     SEED="$2"; shift 2;;
    --base)     BASE="$2"; shift 2;;
    --max-len)  MAXLEN="$2"; shift 2;;
    *) echo "[WARN] 忽略未知參數：$1"; shift;;
  esac
done

# 啟用 .venv（若存在）
if [ -f ".venv/bin/activate" ]; then source ".venv/bin/activate"; echo "[ENV] $(python -V 2>&1)"
else echo "[ENV] 未找到 .venv，使用系統 python：$(python -V 2>&1 || true)"; fi

PY="$(command -v python3 || command -v python || true)"; : "${PY:?找不到 python}"
[ -n "$IN" ] || { echo "[FATAL] 請指定 --in-jsonl <路徑>（不可用自動生成資料）"; exit 90; }
[ -s "$IN" ] || { echo "[FATAL] 找不到或空白：$IN"; exit 91; }
[ -s ".sma_tools/ruleset.yml" ] || { echo "[FATAL] 缺少 .sma_tools/ruleset.yml"; exit 92; }
mkdir -p "$(dirname "$SILV")" "$(dirname "$PRED")" "$MD" reports_auto

# 依賴偵測（缺失則走 regex fallback）
DEPS_MISSING="$("$PY" - <<'PY'
import importlib, json
mods=["yaml","torch","transformers","seqeval"]
miss=[m for m in mods if importlib.util.find_spec(m) is None]
print(",".join(miss))
PY
)"
FALLBACK_REGEX=0
[ -n "$DEPS_MISSING" ] && { echo "[WARN] 缺少依賴：$DEPS_MISSING"; FALLBACK_REGEX=1; }

run_step() {
  local name="$1"; shift
  local out="$LOG_DIR/${TS}_${name// /_}.out"; local err="$LOG_DIR/${TS}_${name// /_}.err"
  echo ""; echo "========== [STEP] $name =========="
  set +e; { "$@"; } > >(tee -a "$out") 2> >(tee -a "$err" >&2); rc=$?; set -e
  if [ $rc -ne 0 ]; then
    echo "---------- [FAIL] $name rc=$rc ----------"
    echo "[stderr 末 60 行]"; tail -n 60 "$err" || true
    echo "[stdout 末 40 行]"; tail -n 40 "$out" || true
    echo "[LOG] $LOG"; exit $rc
  fi
  echo "---------- [OK] $name ----------"
}

# 銀標
run_step "銀標生成" "$PY" .sma_tools/generate_silver_kie.py --in_jsonl "$IN" --out_jsonl "$SILV" --rules ".sma_tools/ruleset.yml"

if [ "$FALLBACK_REGEX" -eq 0 ]; then
  run_step "XLM-R 訓練" "$PY" .sma_tools/train_kie.py --silver "$SILV" --model_dir "$MD" --base_model "$BASE" --epochs "$EPOCHS" --seed "$SEED" --max_len "$MAXLEN"
  run_step "XLM-R 推論" "$PY" .sma_tools/inference_kie.py --model_dir "$MD" --in_jsonl "$IN" --out_jsonl "$PRED" --max_len "$MAXLEN"
  if [ -n "${GOLD:-}" ] && [ -s "$GOLD" ]; then
    run_step "seqeval 評測" "$PY" .sma_tools/eval_kie.py --pred "$PRED" --gold "$GOLD" --model_dir "$MD" --out "reports_auto/kie_eval.txt" --max_len "$MAXLEN"
  else
    echo "[INFO] 未提供 --eval-gold，略過評測"
  fi
else
  echo "[INFO] 轉入 Regex Fallback（僅生成銀標與推論 JSONL）"
  run_step "Regex 銀標/推論" "$PY" - "$IN" <<'PY'
import json,re,sys,os
IN=sys.argv[1]; os.makedirs("data/kie",exist_ok=True); os.makedirs("reports_auto",exist_ok=True)
pat_amount=re.compile(r"(?:NT\\$|USD|\\$)\\s?\\d[\\d,]*(?:\\.\\d+)?")
pat_date  =re.compile(r"(\\d{4}[/-]\\d{1,2}[/-]\\d{1,2}|\\d{1,2}/\\d{1,2})")
pat_env   =re.compile(r"\\b(prod|production|staging|stage|test|dev)\\b", re.I)
def spans(t,rx,l): return [{"start":m.start(),"end":m.end(),"label":l} for m in rx.finditer(t)]
def run(inp,outp):
    n=0
    with open(inp,"r",encoding="utf-8") as fi, open(outp,"w",encoding="utf-8") as fo:
        for ln in fi:
            o=json.loads(ln); t=o.get("text") or o.get("body") or ""
            s=spans(t,pat_amount,"amount")+spans(t,pat_date,"date_time")+spans(t,pat_env,"env")
            fo.write(json.dumps({"text":t,"spans":s},ensure_ascii=False)+"\n"); n+=1
    return n
n1=run(IN,"data/kie/silver.jsonl"); n2=run(IN,"reports_auto/kie_pred.jsonl")
print(f"[OK] SILVER {n1} -> data/kie/silver.jsonl"); print(f"[OK] PRED {n2} -> reports_auto/kie_pred.jsonl")
PY
fi

echo "========== [RESULTS] =========="
[ -s "$SILV" ] && echo " - 銀標：$SILV" || echo " - [MISS] $SILV"
[ -s "$PRED" ] && echo " - 推論：$PRED" || echo " - [MISS] $PRED"
[ -d "$MD" ]   && echo " - 模型：$MD"   || echo " - [MISS] $MD"
[ -s "reports_auto/kie_eval.txt" ] && { echo " - 評測：reports_auto/kie_eval.txt"; tail -n +1 reports_auto/kie_eval.txt; } || echo " - 評測：未產生"
echo "[LOG] $LOG"
