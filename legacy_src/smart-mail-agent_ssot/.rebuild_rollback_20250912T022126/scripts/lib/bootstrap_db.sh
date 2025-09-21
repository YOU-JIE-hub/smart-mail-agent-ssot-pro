#!/usr/bin/env bash
set -e
DB="reports_auto/audit.sqlite3"; mkdir -p "$(dirname "$DB")"
sqlite3 "$DB" <<'SQL'
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS errors (
  id INTEGER PRIMARY KEY,
  ts TEXT, stage TEXT, code TEXT, msg TEXT
);
CREATE TABLE IF NOT EXISTS actions (
  id INTEGER PRIMARY KEY,
  ts TEXT, kind TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  ts TEXT, topic TEXT, data TEXT
);
SQL
echo "[BOOTSTRAP-DB] ready: $DB"
