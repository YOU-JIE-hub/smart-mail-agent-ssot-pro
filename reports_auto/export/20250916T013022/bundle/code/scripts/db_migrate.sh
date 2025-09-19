#!/usr/bin/env bash
set -Eeuo pipefail; ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
DB="reports_auto/audit.sqlite3"; mkdir -p "$(dirname "$DB")"
sqlite3 "$DB" <<'SQL'
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS mails(mail_id TEXT PRIMARY KEY, subject TEXT, sender TEXT, received_at TEXT);
CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY AUTOINCREMENT, mail_id TEXT, action TEXT, params_json TEXT, status TEXT, retries INTEGER DEFAULT 0, started_at TEXT, finished_at TEXT, UNIQUE(mail_id, action));
CREATE TABLE IF NOT EXISTS llm_calls(id INTEGER PRIMARY KEY AUTOINCREMENT, mail_id TEXT, stage TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER, latency_ms INTEGER, cost_usd REAL, request_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS errors(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, stage TEXT, mail_id TEXT, message TEXT);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_llm_calls_stage ON llm_calls(stage);
CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors(ts);
SQL
echo "[OK] DB migrate -> $DB"
