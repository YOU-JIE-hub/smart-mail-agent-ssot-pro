#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[FATAL] not found: $ROOT"; exit 2; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
export SMA_SMTP_MODE="${SMA_SMTP_MODE:-outbox}"
export SMA_LLM_PROVIDER="${SMA_LLM_PROVIDER:-none}"
say(){ echo "[$(date +%H:%M:%S)] $*"; }

say "Run E2E via CLI"
python -u -m smart_mail_agent.cli.e2e --db db/sma.sqlite data/demo_eml

RUN_DIR="$(ls -td reports_auto/e2e_mail/* | head -n1)"
RUN_TS="$(basename "$RUN_DIR")"
say "RUN_DIR=$RUN_DIR  RUN_TS=$RUN_TS"

say "Ensure compatibility views (mails_compat, actions_compat)"
bash -eu <<'BASH_SUB'
DB="db/sma.sqlite"
has_col(){ sqlite3 "$DB" "PRAGMA table_info(actions);" | awk -F'|' -v c="$1" '$2==c{ok=1} END{exit ok?0:1}'; }
if   has_col action_type; then TYPE_COL="action_type"; elif has_col action; then TYPE_COL="action"; else TYPE_COL="NULL"; fi
if   has_col payload_json && has_col payload_ref; then PLOAD_EXPR="COALESCE(payload_json,payload_ref)"
elif has_col payload_json; then PLOAD_EXPR="payload_json"
elif has_col payload_ref;  then PLOAD_EXPR="payload_ref"
else PLOAD_EXPR="NULL"; fi
sqlite3 "$DB" <<SQL
PRAGMA foreign_keys=OFF;
DROP VIEW IF EXISTS mails_compat;
CREATE VIEW mails_compat AS
SELECT COALESCE(id, case_id) AS id, COALESCE(subject,'') AS subject, COALESCE(from_addr,'') AS from_addr, COALESCE(to_addr,'') AS to_addr, received_at, raw_path, created_at
FROM mails;
DROP VIEW IF EXISTS actions_compat;
CREATE VIEW actions_compat AS
SELECT case_id, ${TYPE_COL} AS type, status, idempotency_key, ${PLOAD_EXPR} AS payload_json, created_at, started_at, ended_at, run_ts
FROM actions;
SQL
BASH_SUB

# ★ 新增：先把 approvals 表升級到正確 schema
say "Ensure/migrate approvals schema"
python tools/db_ensure_approvals.py --db db/sma.sqlite

say "Summarize mails (offline)"
python tools/mail_summarize_offline.py --db db/sma.sqlite --run-dir "$RUN_DIR"

say "Generate actions_plan (v3)"
python tools/generate_actions_plan_v3.py --db db/sma.sqlite --run-dir "$RUN_DIR" --hil-thr "${SMA_HIL_THR:-0.80}"

say "Seed approvals from plan (HIL)"
python tools/approvals_seed_from_plan.py --db db/sma.sqlite --run-dir "$RUN_DIR"

say "Sync actions_plan → DB(actions)"
python tools/sync_actions_plan_to_db.py --db db/sma.sqlite --run-dir "$RUN_DIR"

say "Apply actions (offline)"
python tools/apply_actions_plan.py --db db/sma.sqlite --run-dir "$RUN_DIR"

say "Backfill actions state from FS"
python tools/actions_backfill_from_fs.py --db db/sma.sqlite --run-dir "$RUN_DIR"

say "Materialize + Backfill outstanding planned actions"
bash tools/materialize_missing_artifacts.sh "$RUN_DIR"
say "Refresh SUMMARY"
python tools/summary_refresh.py "$RUN_DIR"

say "Project audit"
bash tools/project_audit.sh >/dev/null || true

say "Emit NDJSON event"
python tools/emit_event.py --run-ts "$RUN_TS" --stage "oneclick" --status "ok"

say "DB snapshot (this run) via view"
sqlite3 db/sma.sqlite "SELECT type, status, COUNT(*) FROM actions_compat WHERE run_ts='$RUN_TS' GROUP BY 1,2 ORDER BY 1,2;"

say "Artifacts produced (top)"
find "$RUN_DIR/rpa_out" -maxdepth 2 -type f | sed -n '1,12p' || true

say "SUMMARY tail"
tail -n 40 "$RUN_DIR/SUMMARY.md" || true

say "DONE → $RUN_DIR"
