#!/usr/bin/env bash
# Phase12 — 內嵌守護遷移 → 嚴格守門 → 健康檢查 → 審計輸出（無外部依賴）
set -Eeuo pipefail
trap 'ec=$?; echo "[ERR] line:$LINENO cmd:${BASH_COMMAND} (exit=$ec)" >&2; exit $ec' ERR
export LC_ALL=C.UTF-8

ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
[[ -d "$ROOT" ]] || { echo "[FATAL] project root missing: $ROOT" >&2; exit 96; }
cd "$ROOT"

TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports_auto/{logs,status}
STATUS="reports_auto/status/PHASE12_${TS}.md"
LOG="reports_auto/logs/PHASE12_${TS}.log"
if command -v stdbuf >/dev/null 2>&1; then exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1; else exec > >(tee -a "$LOG") 2>&1; fi

echo "=== [ENV] ==="
if [[ -x .venv_clean/bin/activate ]]; then . .venv_clean/bin/activate
elif [[ -x .venv/bin/activate ]]; then . .venv/bin/activate
fi
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python -V || true
echo

DB="reports_auto/audit.sqlite3"
[[ -f "$DB" ]] || { echo "[FATAL] DB not found: $DB" >&2; exit 97; }

echo "[STEP] Embedded guarded migration + 去重/補鍵（tables/columns/indexes/trigger/views）"
python - <<'PY'
import sqlite3, json, os
from pathlib import Path
db=Path("reports_auto/audit.sqlite3"); db.parent.mkdir(parents=True, exist_ok=True)
conn=sqlite3.connect(db); cur=conn.cursor()
cur.execute("PRAGMA journal_mode=WAL"); cur.execute("PRAGMA foreign_keys=ON")

def table_exists(t): return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone() is not None
def cols(t): return {r[1] for r in cur.execute(f"PRAGMA table_info({t})")}
def add_col(t, name, decl):
    if name not in cols(t):
        cur.execute(f"ALTER TABLE {t} ADD COLUMN {name} {decl}")

# 基礎表
base = {
  "actions":[("ts","INTEGER"),("mail_id","TEXT"),("intent","TEXT"),("action","TEXT"),("idempotency_key","TEXT"),("priority","TEXT"),("queue","TEXT"),("status","TEXT"),("payload","TEXT")],
  "mails":[("mail_id","TEXT PRIMARY KEY"),("subject","TEXT"),("ts","INTEGER")],
  "errors":[("ts","INTEGER"),("stage","TEXT"),("mail_id","TEXT"),("type","TEXT"),("message","TEXT"),("traceback","TEXT"),("extra","TEXT")],
}
for t, spec in base.items():
    if not table_exists(t):
        cur.execute(f"CREATE TABLE {t} ({', '.join(' '.join(x) for x in spec)})")

# 產品表（最小可運行欄位）
expect = {
  "tickets":[("ts","INTEGER"),("mail_id","TEXT"),("title","TEXT"),("severity","TEXT"),("status","TEXT"),("extra","TEXT"),("idempotency_key","TEXT")],
  "answers":[("ts","INTEGER"),("mail_id","TEXT"),("intent","TEXT"),("answer","TEXT"),("status","TEXT"),("idempotency_key","TEXT"),
             ("source","TEXT"),("kb_hits","INTEGER"),("latency_ms","INTEGER"),("content","TEXT")],
  "changes":[("ts","INTEGER"),("mail_id","TEXT"),("before","TEXT"),("after","TEXT"),("diff","TEXT"),("status","TEXT"),("idempotency_key","TEXT")],
  "quotes":[("ts","INTEGER"),("mail_id","TEXT"),("pdf_path","TEXT"),("amount","REAL"),("currency","TEXT"),("status","TEXT"),("idempotency_key","TEXT")],
  "alerts":[("ts","INTEGER"),("mail_id","TEXT"),("channel","TEXT"),("message","TEXT"),("status","TEXT"),("idempotency_key","TEXT")],
}
for t, spec in expect.items():
    if not table_exists(t):
        cur.execute(f"CREATE TABLE {t} ({', '.join(' '.join(x) for x in spec)})")
    else:
        for c, d in spec:
            add_col(t, c, d)

# —— 關鍵修復：補鍵 + 去重（避免 UNIQUE 索引建立失敗）——
import random, string
def rand8(): return ''.join(random.choice(string.hexdigits.lower()) for _ in range(8))
for t in ("tickets","answers","changes","quotes","alerts"):
    # 先把空或 NULL 的 idempotency_key 補成 唯一鍵
    cur.execute(f"""
        UPDATE {t}
        SET idempotency_key = ( 'fix:{t}:' || hex(randomblob(8)) )
        WHERE idempotency_key IS NULL OR idempotency_key='';
    """)
    # 再刪除重複鍵，只留 rowid 最小的一筆
    # 注意：SQLite 允許多個 NULL，但我們上一步已把空/NULL 都補成唯一值
    cur.execute(f"""
        DELETE FROM {t}
        WHERE rowid NOT IN (
          SELECT MIN(rowid) FROM {t} GROUP BY idempotency_key
        )
    """)

# 索引與觸發器
cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_idem ON actions(idempotency_key)")
for t in ("tickets","answers","changes","quotes","alerts"):
    cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{t}_idem ON {t}(idempotency_key)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)")
cur.execute("""CREATE TABLE IF NOT EXISTS actions_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, idempotency_key TEXT, old_status TEXT, new_status TEXT
)""")
cur.execute("""CREATE TRIGGER IF NOT EXISTS trg_actions_status
AFTER UPDATE OF status ON actions
WHEN old.status IS NOT new.status
BEGIN
  INSERT INTO actions_history(ts,idempotency_key,old_status,new_status)
  VALUES(strftime('%s','now'), NEW.idempotency_key, OLD.status, NEW.status);
END;""")

# 兼容視圖（可查報表）
def ensure_view(name, sql):
    row=cur.execute("SELECT 1 FROM sqlite_master WHERE type='view' AND name=?", (name,)).fetchone()
    if not row: cur.execute(sql)
ensure_view("v_tickets","CREATE VIEW v_tickets AS SELECT ts, mail_id, title, severity, status, idempotency_key, extra AS payload FROM tickets")
ensure_view("v_answers","CREATE VIEW v_answers AS SELECT ts, mail_id, intent, answer, status, idempotency_key, source, kb_hits, latency_ms, content FROM answers")

conn.commit(); conn.close()
print(json.dumps({"migrated":"ok"}, ensure_ascii=False))
PY

echo "[STEP] Attempt queued replay x2（若 CLI 存在；不存在就略過）"
( python -m smart_mail_agent.cli.replay_actions || true )
( python -m smart_mail_agent.cli.replay_actions || true )

echo "[STEP] Strict gate（error/queued 必須為 0）"
python - <<'PY'
import sqlite3, json, sys
conn=sqlite3.connect("reports_auto/audit.sqlite3"); c=conn.cursor()
done=c.execute("SELECT COUNT(*) FROM actions WHERE status='done'").fetchone()[0]
error=c.execute("SELECT COUNT(*) FROM actions WHERE status='error'").fetchone()[0]
queued=c.execute("SELECT COUNT(*) FROM actions WHERE status='queued'").fetchone()[0]
hist=dict(c.execute("SELECT status, COUNT(*) FROM actions GROUP BY status").fetchall())
print("[FINAL]", json.dumps({"done":done,"error":error,"queued":queued,"hist":hist}, ensure_ascii=False))
conn.close()
if error>0 or queued>0: sys.exit(90)
PY

echo "[STEP] Health checks"
sqlite3 "$DB" <<'SQL'
.headers off
.mode list
SELECT '[HIST]', status, COUNT(*) FROM actions GROUP BY status;
SELECT '[HISTORY10]', datetime(ts,'unixepoch'), idempotency_key, old_status, new_status
FROM actions_history ORDER BY ts DESC LIMIT 10;
SELECT '[V_TICKETS_CNT]', COUNT(*) FROM v_tickets LIMIT 1;
SELECT '[V_ANSWERS_CNT]', COUNT(*) FROM v_answers LIMIT 1;
SELECT '[ERRORS_TOP]', datetime(ts,'unixepoch'), stage, mail_id, message
FROM errors ORDER BY ts DESC LIMIT 5;
SQL

# 寫審計
{
  echo "# PHASE12 @ ${TS}"
  echo
  echo "## 內容"
  echo "- 內嵌遷移：補欄位/索引/觸發器 + 去重/補鍵防唯一索引炸裂"
  echo "- 嘗試回放兩次（若 CLI 存在）"
  echo "- 嚴格守門（error/queued 為 0）"
  echo "- 健康檢查（直方圖/歷程/視圖/錯誤）"
  echo
  echo "## 日誌"
  echo "- ${LOG}"
} > "$STATUS"

echo "[DONE] Phase-12 完成。審計: $STATUS ; 日誌: $LOG"
