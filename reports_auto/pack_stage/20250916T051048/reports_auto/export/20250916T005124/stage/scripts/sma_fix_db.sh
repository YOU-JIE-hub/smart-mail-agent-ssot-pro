#!/usr/bin/env bash
set -Eeuo pipefail
DB="db/sma.sqlite"
[ -f "$DB" ] || { echo "[INFO] 跳過，無 sqlite"; exit 0; }
python - <<'PY'
import sqlite3, os, sys
db="db/sma.sqlite"
conn=sqlite3.connect(db); cur=conn.cursor()
def cols(t): return [r[1] for r in cur.execute(f'PRAGMA table_info({t})')]
# intent_preds：補 label 欄位，若有舊欄位 intent 則回填
if 'intent_preds' in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cs=cols('intent_preds')
    if 'label' not in cs:
        cur.execute('ALTER TABLE intent_preds ADD COLUMN label TEXT')
        if 'intent' in cs:
            cur.execute('UPDATE intent_preds SET label=COALESCE(label,intent)')
    if 'created_at' not in cs:
        cur.execute('ALTER TABLE intent_preds ADD COLUMN created_at TEXT')
# kie_spans / err_log：補齊欄位
if 'kie_spans' in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cs=cols('kie_spans')
    for col,ddl in [('case_id','case_id TEXT'),('key','"key" TEXT'),('value','value TEXT'),('start','start INT'),('end','"end" INT')]:
        if col not in cs: cur.execute(f'ALTER TABLE kie_spans ADD COLUMN {ddl}')
if 'err_log' in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cs=cols('err_log')
    for col,ddl in [('ts','ts TEXT'),('case_id','case_id TEXT'),('err','err TEXT')]:
        if col not in cs: cur.execute(f'ALTER TABLE err_log ADD COLUMN {ddl}')
conn.commit(); conn.close()
print("[OK] DB schema fixed")
PY
