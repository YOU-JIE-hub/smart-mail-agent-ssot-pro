#!/usr/bin/env bash
# Phase13 — 乾淨環境（不汙染）+ 產物打包 + 24h 健康報告 + 嚴格守門
set -Eeuo pipefail
trap 'ec=$?; echo "[ERR] line:$LINENO cmd:${BASH_COMMAND} (exit=$ec)" >&2; exit $ec' ERR
export LC_ALL=C.UTF-8

ROOT="${SMA_ROOT:-$PWD}"
[[ -d "$ROOT" ]] || { echo "[FATAL] project root missing: $ROOT" >&2; exit 96; }
cd "$ROOT"

TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports_auto/{logs,status,artifacts} scripts
STATUS="reports_auto/status/PHASE13_${TS}.md"
LOG="reports_auto/logs/PHASE13_${TS}.log"
if command -v stdbuf >/dev/null 2>&1; then exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1; else exec > >(tee -a "$LOG") 2>&1; fi

echo "=== [ENV] ==="
python -V || true
echo

# ------------------------------
# 1) 乾淨環境 — 僅在 .venv_clean 安裝，禁止污染全域 pip
# ------------------------------
cat > scripts/bootstrap_env.sh <<'SB'
#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT"
VENV=".venv_clean"
PY="${PYTHON_BIN:-python3}"

if [[ ! -d "$VENV" ]]; then
  echo "[BOOT] create venv at $VENV"
  "$PY" -m venv "$VENV"
fi

# 只允許在 venv 內 pip；避免汙染系統或使用者站台套件
set +u
source "$VENV/bin/activate"
set -u
export PIP_REQUIRE_VIRTUALENV=1
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
python -V

if [[ -f requirements.txt ]]; then
  echo "[BOOT] install requirements in venv (no global pollution)"
  python -m pip install --upgrade pip
  python -m pip install --no-cache-dir -r requirements.txt
else
  echo "[BOOT] no requirements.txt, skip"
fi
echo "[BOOT] ok"
SB
chmod +x scripts/bootstrap_env.sh

echo "[STEP] bootstrap venv (no pollution)"
scripts/bootstrap_env.sh
set +u; source .venv_clean/bin/activate; set -u
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

# ------------------------------
# 2) 產物打包（DB+logs+status）— 交付/留痕
# ------------------------------
cat > scripts/ship_artifacts.sh <<'SA'
#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT"
mkdir -p reports_auto/artifacts
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/artifacts/sma_bundle_${TS}.tar.gz"
tar -czf "$OUT" reports_auto/audit.sqlite3 reports_auto/logs reports_auto/status 2>/dev/null || true
echo "$OUT"
SA
chmod +x scripts/ship_artifacts.sh

# ------------------------------
# 3) 24h 健康報告（Markdown）— 嚴格避開保留字
# ------------------------------
cat > scripts/report_24h.sh <<'RPT'
#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT"
DB="reports_auto/audit.sqlite3"
[[ -f "$DB" ]] || { echo "[FATAL] missing DB: $DB" >&2; exit 97; }

TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/status/REPORT_24H_${TS}.md"

{
  echo "# REPORT_24H @ ${TS}"
  echo
  echo "## actions 直方圖"
  sqlite3 "$DB" "SELECT status, COUNT(*) FROM actions GROUP BY status;" | sed 's/^/- /'
  echo
  echo "## intents 分布（24h）"
  sqlite3 "$DB" "SELECT intent, COUNT(*) FROM actions WHERE ts >= strftime('%s','now','-1 day') GROUP BY intent ORDER BY 2 DESC;" | sed 's/^/- /'
  echo
  echo "## 最近 errors（最多 10 筆）"
  sqlite3 "$DB" "SELECT datetime(ts,'unixepoch') AS ts_human, stage, mail_id, message FROM errors ORDER BY ts DESC LIMIT 10;" \
    | sed 's/^/- /'
  echo
  echo "## actions_history 近 20 筆"
  sqlite3 "$DB" "SELECT datetime(ts,'unixepoch'), idempotency_key, old_status, new_status FROM actions_history ORDER BY ts DESC LIMIT 20;" \
    | sed 's/^/- /'
  echo
  if sqlite3 "$DB" "SELECT 1 FROM sqlite_master WHERE type='view' AND name='v_tickets';" | grep -q 1; then
    echo "## v_tickets / v_answers 計數"
    echo "- tickets: $(sqlite3 "$DB" "SELECT COUNT(*) FROM v_tickets;")"
    echo "- answers: $(sqlite3 "$DB" "SELECT COUNT(*) FROM v_answers;")"
    echo
  fi
} > "$OUT"

echo "$OUT"
RPT
chmod +x scripts/report_24h.sh

# ------------------------------
# 4) 跑 Phase-12（保險再驗一次收斂）
# ------------------------------
if [[ -f "sma_phase12_ci_ship.sh" ]]; then
  echo "[STEP] rerun Phase-12 to ensure convergence"
  bash sma_phase12_ci_ship.sh
else
  echo "[STEP] Phase-12 script not found, skip rerun (ok)"
fi

# ------------------------------
# 5) 生成 24h 健康報告 + 打包產物 + 嚴格守門
# ------------------------------
RPT_FILE="$(scripts/report_24h.sh)"
BUNDLE="$(scripts/ship_artifacts.sh)"
echo "[BUNDLE] $BUNDLE"
echo "[REPORT] $RPT_FILE"

# 守門：error / queued 都必須 0
ERR=$(sqlite3 reports_auto/audit.sqlite3 "SELECT COUNT(*) FROM actions WHERE status='error';")
QUE=$(sqlite3 reports_auto/audit.sqlite3 "SELECT COUNT(*) FROM actions WHERE status='queued';")
HIST=$(sqlite3 reports_auto/audit.sqlite3 "SELECT group_concat(status||'='||cnt,';') FROM (SELECT status, COUNT(*) as cnt FROM actions GROUP BY status);")
echo "[FINAL] hist: ${HIST:-N/A}  error=${ERR}  queued=${QUE}"
if [[ "$ERR" -eq 0 && "$QUE" -eq 0 ]]; then
  EC=0
else
  EC=90
fi

# 寫審計摘要
{
  echo "# PHASE13 @ ${TS}"
  echo
  echo "## 做了什麼"
  echo "- 乾淨 venv：只在 .venv_clean 安裝（PIP_REQUIRE_VIRTUALENV=1），避免污染系統/使用者環境"
  echo "- 交付產物：DB+logs+status 打包 -> ${BUNDLE}"
  echo "- 24h 健康報告：${RPT_FILE}"
  echo "- 嚴格守門：error=${ERR} queued=${QUE}"
  echo
  echo "## 下一步（可選）"
  echo "- 在 CI 增加 artifact 上傳：把 ${BUNDLE} 作為 build 產物"
  echo "- 每日排程產出 report_24h（cron / GitHub Actions schedule）"
} > "$STATUS"

echo "[DONE] Phase-13 完成。審計: $STATUS ; 日誌: $LOG"
exit $EC
