#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$PWD}"
cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
DIAG="reports_auto/diag/$TS"; mkdir -p "$DIAG"

# 進 venv
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi
# 設 PYTHONPATH（關鍵！）
export PYTHONPATH="$ROOT:$ROOT/src:${PYTHONPATH:-}"

# 偵測/設定 KIE 權重（你實際的權重路徑在 /home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model）
: "${KIE_MODEL_DIR:=}"
if [ -z "$KIE_MODEL_DIR" ]; then
  for cand in \
    "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model" \
    "$ROOT/../smart-mail-agent_ssot/artifacts_inbox/kie1/model" \
    "$ROOT/artifacts_inbox/kie1/model" \
    "$ROOT/artifacts/kie/model" \
    "$ROOT/model" ; do
    if [ -d "$cand" ] && [ -s "$cand/config.json" ]; then export KIE_MODEL_DIR="$cand"; break; fi
  done
fi
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

# 記錄環境
python - <<'PY' > "$DIAG/env.json" || true
import os, sys, json
print(json.dumps({
  "python": sys.version,
  "executable": sys.executable,
  "cwd": os.getcwd(),
  "PYTHONPATH": os.environ.get("PYTHONPATH",""),
  "env": {k: os.environ.get(k,"") for k in ("SMA_INTENT_ML_PKL","KIE_MODEL_DIR","TRANSFORMERS_OFFLINE")}
}, ensure_ascii=False, indent=2))
PY

run() {  # name, cmd...
  local name="$1"; shift
  echo "[RUN] $name :: $*" | tee "$DIAG/$name.cmd"
  mkdir -p "$DIAG/$name"
  ( set +e
    { "$@" ; } >"$DIAG/$name/stdout.log" 2>"$DIAG/$name/stderr.log"
    echo $? > "$DIAG/$name/rc.txt"
  )
  echo "[RC] $name -> $(cat "$DIAG/$name/rc.txt")"
}

# 步驟：DB
run db.migrate  python tools/db_migrate.py migrate
run db.views    python tools/db_migrate.py views
run db.snapshot python tools/db_migrate.py snapshot

# TRI
run tri         python tools/tri_suite.py

# KIE eval（自動挑資料）
IN=""
[ -s data/kie/test_real.jsonl ] && IN=data/kie/test_real.jsonl
[ -z "$IN" ] && [ -s data/kie/test.jsonl ] && IN=data/kie/test.jsonl
if [ -z "$IN" ] && [ -s fixtures/eval_set.jsonl ]; then
  mkdir -p reports_auto/kie
  python - <<'PYX' < fixtures/eval_set.jsonl > reports_auto/kie/_from_fixtures.jsonl
import sys, json
for ln in sys.stdin:
    try:
        o=json.loads(ln); e=o.get("email",{})
        t=(e.get("subject","") + "\n" + e.get("body","")).strip()
        print(json.dumps({"text": t}, ensure_ascii=False))
    except Exception:
        pass
PYX
  IN=reports_auto/kie/_from_fixtures.jsonl
fi
if [ -n "$IN" ]; then
  OUT="reports_auto/kie/pred_${TS}.jsonl"
  run kie.eval    python tools/kie/eval.py "$IN" "$OUT"
  echo "$OUT" > reports_auto/kie/_last_pred.txt
  if [ -s data/kie/test.jsonl ]; then
    run kie.score  python tools/kie/score_spans.py
  fi
else
  echo "no KIE input" | tee "$DIAG/kie.eval/no_input.txt"
fi

# Spam 指標
run spam       python tools/spam_report.py

# ML 弱訊號
run ml.signal  python tools/log_ml_signals.py

# 收尾：輸出 diag 目錄
echo "{\"diag_dir\":\"$DIAG\"}"
