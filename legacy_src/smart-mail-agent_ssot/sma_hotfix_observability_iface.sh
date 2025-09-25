#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
mkdir -p reports_auto/{logs,status} src/smart_mail_agent/observability
TS="$(date +%Y%m%dT%H%M%S)"
STATUS="reports_auto/status/HOTFIX_OBSERVABILITY_${TS}.md"
LOG="reports_auto/logs/HOTFIX_OBSERVABILITY_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

if [[ -x .venv/bin/activate ]]; then . .venv/bin/activate; fi
export PYTHONNOUSERSITE=1
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python -V

# 1) 強化 audit_db.py（提供 ensure_schema / open_db / insert_row / write_err_log）
AUD="src/smart_mail_agent/observability/audit_db.py"
cp -f "$AUD" "${AUD}.bak.${TS}" 2>/dev/null || true
cat > "$AUD" <<'PY'
from __future__ import annotations
import os, json, time, sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Iterable

# 統一 DB 位置：$SMA_ROOT/reports_auto/audit.sqlite3（可用 SMA_DB_PATH 覆蓋）
def _root() -> Path:
    return Path(os.environ.get("SMA_ROOT", Path(__file__).resolve().parents[3]))

DEFAULT_DB: str = os.environ.get(
    "SMA_DB_PATH",
    str(_root() / "reports_auto" / "audit.sqlite3"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS mails    (mail_id TEXT PRIMARY KEY, subject TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS actions  (ts INTEGER, mail_id TEXT, intent TEXT, action TEXT,
                                     idempotency_key TEXT UNIQUE, priority TEXT, queue TEXT, status TEXT DEFAULT 'queued');
CREATE TABLE IF NOT EXISTS metrics  (ts INTEGER, stage TEXT, duration_ms INTEGER, ok INTEGER, extra TEXT);
CREATE TABLE IF NOT EXISTS tickets  (ts INTEGER, mail_id TEXT, type TEXT, status TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS quotes   (ts INTEGER, mail_id TEXT, file_path TEXT, amount REAL, status TEXT);
CREATE TABLE IF NOT EXISTS answers  (ts INTEGER, mail_id TEXT, source TEXT, kb_hits INTEGER, latency_ms INTEGER, content TEXT);
CREATE TABLE IF NOT EXISTS changes  (ts INTEGER, mail_id TEXT, diff_json TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS alerts   (ts INTEGER, mail_id TEXT, severity TEXT, channel TEXT, message TEXT);
"""

def ensure_schema(db_path: Optional[str] = None) -> str:
    """確保 DB 與資料表存在，回傳 DB 路徑字串。"""
    db = Path(db_path or DEFAULT_DB)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()
    return str(db)

def open_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """開啟 DB（若尚未建表會先 ensure_schema）。"""
    ensure_schema(db_path)
    return sqlite3.connect(db_path or DEFAULT_DB)

def _json(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return json.dumps({"_unjsonable": str(x)}, ensure_ascii=False)

def insert_row(table: str, row: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """通用 insert：欄位字典 -> INSERT；自動 ensure_schema。"""
    con = open_db(db_path)
    try:
        cols = list(row.keys())
        vals = [row[c] for c in cols]
        # 對 dict/list 之類做 JSON 化，避免 sqlite type 錯誤
        vals = [(_json(v) if isinstance(v, (dict, list)) else v) for v in vals]
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})"
        con.execute(sql, vals)
        con.commit()
    finally:
        con.close()

def _log_dir() -> Path:
    p = _root() / "reports_auto" / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p

def write_err_log(stage: str, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> Path:
    """將錯誤或重要事件寫入 JSONL 檔（pipeline.ndjson），並鏡射到單獨 crash 檔（若 level 為 ERROR）。"""
    rec = {"ts": int(time.time()), "stage": stage, "level": level, "message": message, **(extra or {})}
    log_dir = _log_dir()
    nd = log_dir / "pipeline.ndjson"
    with nd.open("a", encoding="utf-8") as f:
        f.write(_json(rec) + "\n")
    if level.upper() in ("ERROR", "FATAL"):
        crash = log_dir / f"CRASH_{time.strftime('%Y%m%dT%H%M%S')}.log"
        with crash.open("w", encoding="utf-8") as f:
            f.write("# CRASH MIRROR (from audit_db.write_err_log)\n")
            f.write(_json(rec) + "\n")
    return nd

__all__ = (
    "DEFAULT_DB",
    "SCHEMA",
    "ensure_schema",
    "open_db",
    "insert_row",
    "write_err_log",
)
PY

# 2) 穩定 __init__.py（顯式再匯出，避免名稱變動時 ImportError）
PKG_INIT="src/smart_mail_agent/observability/__init__.py"
cp -f "$PKG_INIT" "${PKG_INIT}.bak.${TS}" 2>/dev/null || true
cat > "$PKG_INIT" <<'PY'
from __future__ import annotations
# 統一從 audit_db 匯出供外部使用；若未來擴充其他模組，這裡保持穩定 API
from .audit_db import (
    DEFAULT_DB,
    SCHEMA,
    ensure_schema,
    open_db,
    insert_row,
    write_err_log,
)

__all__ = [
    "DEFAULT_DB",
    "SCHEMA",
    "ensure_schema",
    "open_db",
    "insert_row",
    "write_err_log",
]
PY

# 3) 最小格式化（僅在本地 venv 有工具時；失敗不阻斷）
set +e
python -m ruff check src --fix 2>/dev/null || true
python -m black -q src 2>/dev/null || true
set -e

# 4) Smoke：可否 import / 呼叫 ensure_schema
python - <<'PY'
import os
os.environ.setdefault("SMA_ROOT", os.getcwd())
from smart_mail_agent.observability import ensure_schema, DEFAULT_DB
p = ensure_schema()
print("[SMOKE] ensure_schema ok ->", p)
print("[SMOKE] DEFAULT_DB =", DEFAULT_DB)
PY

# 5) 快速驗收（若 pytest 存在）
set +e
python -m pytest -q -rA 2>/dev/null
EE=$?
python -X faulthandler -u -m smart_mail_agent.cli.e2e_safe 2>/dev/null
EC=$?
set -e

# 6) 寫審計
{
  echo "# HOTFIX_OBSERVABILITY @ ${TS}"
  echo
  echo "## files"
  echo "- updated: ${AUD}"
  echo "- updated: ${PKG_INIT}"
  echo
  echo "## quick-check"
  echo "- pytest exit: ${EE}"
  echo "- e2e exit: ${EC}"
} > "$STATUS"

echo "[DONE] Observability hotfix 完成。審計: $STATUS ; 日誌: $LOG"
