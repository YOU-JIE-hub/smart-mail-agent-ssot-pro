#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[FATAL] not found: $ROOT"; exit 2; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

APPROVE_ALL=0
SMTP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --approve-all) APPROVE_ALL=1; shift;;
    --smtp) SMTP=1; shift;;
    *) echo "[WARN] unknown arg: $1"; shift;;
  esac
done

say(){ echo "[$(date +%H:%M:%S)] $*"; }

# 1) 跑主流程（E2E：摘要→計劃→seed HIL→sync→apply→backfill→SUMMARY）
bash tools/one_click_s2s3s5.sh

# 2) 最新批
RUN_DIR="$(ls -td reports_auto/e2e_mail/* | head -n1)"
RUN_TS="$(basename "$RUN_DIR")"
say "RUN_DIR=$RUN_DIR"

# 3) （可選）全數核准 HIL（只限 SendEmail）
if [[ $APPROVE_ALL -eq 1 ]]; then
  say "HIL approve all (SendEmail)"
  sqlite3 db/sma.sqlite "
    UPDATE approvals
       SET status='approved', decided_at=datetime('now')
     WHERE run_ts='$RUN_TS'
       AND status='pending'
       AND (action_type='SendEmail' OR action_type IS NULL);"
  sqlite3 db/sma.sqlite "
    UPDATE actions
       SET status='planned', updated_at=datetime('now')
     WHERE run_ts='$RUN_TS'
       AND COALESCE(action_type,action)='SendEmail'
       AND status='skipped_by_hil';"
fi

# 4) 若是 SMTP 模式：不要 materialize SendEmail；其餘（Ticket/Quote/Diff/FAQ）允許補檔
if [[ ${SMA_SMTP_MODE:-outbox} == "smtp" || $SMTP -eq 1 ]]; then
  export SMA_SMTP_MODE=smtp
  say "SMTP mode ON (SendEmail will attempt real delivery)"
  # 只 materialize 非 SendEmail 類型（避免把 SendEmail蓋成 downgraded）
  bash -c '
    set -e
    RUN_DIR="'"$RUN_DIR"'"
    # 暫時把 materializer 裡的 SendEmail 流程跳過：用 grep -v
    tmp="$(mktemp)"; trap "rm -f $tmp" EXIT
    sed "/make_mailout/d" tools/materialize_missing_artifacts.sh > "$tmp"
    bash "$tmp" "$RUN_DIR"
  '
else
  # outbox 模式：可全量補檔（會顯示 downgraded: outbox）
  bash tools/materialize_missing_artifacts.sh "$RUN_DIR"
fi

# 5) 回填 + SUMMARY + 快照
python tools/actions_backfill_from_fs.py --db db/sma.sqlite --run-dir "$RUN_DIR" -v
python tools/summary_refresh.py "$RUN_DIR"
sqlite3 db/sma.sqlite "
  SELECT type, status, COUNT(*) FROM actions_compat
  WHERE run_ts='$RUN_TS' GROUP BY 1,2 ORDER BY 1,2;" | sed 's/^/[SNAP] /'

# 6) 遮罩敏感資訊輸出
[ -n "${SMA_SMTP_PASS: "***REDACTED***"
say "SMTP_USER=${SMA_SMTP_USER:-unset}  SMTP_PASS=${SAY_PASS}"
