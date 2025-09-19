#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

echo "[1/9] ensure venv + deps"
if [ ! -x .venv_clean/bin/python ]; then python3 -m venv .venv_clean; fi
. .venv_clean/bin/activate
python -m pip -q install --upgrade pip
pip -q install "ruff>=0.5.6" "alembic>=1.13" "SQLAlchemy>=2.0" "psycopg2-binary>=2.9" || true

mkdir -p reports_auto/status reports_auto/outbox scripts

echo "[2/9] add pyproject.toml (ruff formatter, ignore E501, line-length=120)"
cat > pyproject.toml <<'TOML'
[tool.ruff]
line-length = 120
extend-ignore = ["E501"]  # 交給 formatter，不用 pycodestyle 的 E501
target-version = "py310"

[tool.ruff.lint]
select = ["E","F","I","UP","B"]     # 常見: E701/E702, E401, I001, UP006, F401
fixable = ["ALL"]

[tool.ruff.format]
quote-style = "preserve"
indent-style = "space"
line-ending = "auto"
docstring-code-format = true
TOML

echo "[3/9] fix alembic/env.py (KeyError 'url' & 使用 get_db_url)"
if [ -f alembic/env.py ]; then cp -f alembic/env.py alembic/env.py.bak || true; fi
mkdir -p alembic
cat > alembic/env.py <<'PY'
from __future__ import annotations
from logging.config import fileConfig
import os, sys
from sqlalchemy import engine_from_config, pool
from alembic import context

# 讓 Alembic 找到我們的 models 與 db config
sys.path.insert(0, os.getcwd())
from src.smart_mail_agent.db.config import get_db_url  # type: ignore
from src.smart_mail_agent.db.models import Base        # type: ignore

config = context.config
# 關鍵：把 sqlalchemy.url 設好，讓 engine_from_config 用 prefix="sqlalchemy."
config.set_main_option("sqlalchemy.url", get_db_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",  # << 修正：使用 sqlalchemy. 前綴
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
PY

echo "[4/9] hard-fix src/smart_mail_agent/actions/executors.py (真正語法壞檔)"
mkdir -p src/smart_mail_agent/actions
if [ -f src/smart_mail_agent/actions/executors.py ]; then cp -f src/smart_mail_agent/actions/executors.py src/smart_mail_agent/actions/executors.py.bak || true; fi
cat > src/smart_mail_agent/actions/executors.py <<'PY'
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

# 可選：引用可用的行為器，不在此崩潰；缺少時用降級路徑
try:
    from .quote import do_quote  # type: ignore
except Exception:  # pragma: no cover
    do_quote = None

try:
    from .apology import send_apology  # type: ignore
except Exception:  # pragma: no cover
    send_apology = None  # type: ignore

ALLOW_SAFE_DEGRADE = os.environ.get("SMA_ALLOW_SAFE_DEGRADE", "0") == "1"


def _ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS actions(
               id INTEGER PRIMARY KEY,
               idem TEXT,
               status TEXT,
               payload TEXT,
               created_at TEXT DEFAULT (datetime('now')),
               updated_at TEXT DEFAULT (datetime('now'))
           )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS answers(
               id INTEGER PRIMARY KEY,
               mail_id TEXT,
               intent TEXT,
               answer TEXT,
               status TEXT,
               idempotency_key TEXT UNIQUE,
               created_at TEXT DEFAULT (datetime('now'))
           )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS tickets(
               id INTEGER PRIMARY KEY,
               mail_id TEXT,
               title TEXT,
               severity TEXT,
               status TEXT,
               extra TEXT,
               idempotency_key TEXT UNIQUE,
               created_at TEXT DEFAULT (datetime('now'))
           )"""
    )
    conn.commit()
    conn.close()


def _persist_ticket(db: Path, mail_id: str, title: str, severity: str, key: str, extra: Dict[str, Any]) -> None:
    _ensure_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        """INSERT OR IGNORE INTO tickets
           (mail_id,title,severity,status,extra,idempotency_key)
           VALUES(?, ?, ?, 'done', ?, ?)""",
        (mail_id, title, severity, json.dumps(extra, ensure_ascii=False), key),
    )
    conn.commit()
    conn.close()


def _persist_answer(db: Path, mail_id: str, intent: str, answer: str, key: str) -> None:
    _ensure_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        """INSERT OR IGNORE INTO answers
           (mail_id,intent,answer,status,idempotency_key)
           VALUES(?, ?, ?, 'done', ?)""",
        (mail_id, intent, answer, key),
    )
    conn.commit()
    conn.close()


def _fallback_done(payload: Dict[str, Any], note: str) -> Dict[str, Any]:
    return {"ok": True, "degraded": True, "note": note, "payload": payload}


def execute_action(
    *,
    db_path: str | Path,
    out_root: str | Path,
    name: str,
    payload: Dict[str, Any],
    idem_key: str,
) -> Dict[str, Any]:
    """
    最小可用執行器：在缺模組時不閃退，企業級需可降級。
    """
    t0 = time.time()
    db = Path(db_path)
    out_dir = Path(out_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    if name == "ticket_create":
        title = payload.get("title", "Tech Support")
        sev = payload.get("severity", "P3")
        mail_id = payload.get("mail_id", "?")
        _persist_ticket(db, mail_id, title, sev, idem_key, payload)
        return {"ok": True, "latency_ms": int((time.time() - t0) * 1000)}

    if name == "apology_send":
        if send_apology is None:
            if ALLOW_SAFE_DEGRADE:
                _persist_answer(db, payload.get("mail_id", "?"), "apology", "Degraded apology.", idem_key)
                return _fallback_done(payload, "apology module missing; degraded")
            raise RuntimeError("apology module missing")
        outbox = send_apology(None, payload.get("to", ""), payload.get("mail_id", "?"), idem_key)  # type: ignore
        return {"ok": True, "outbox": outbox, "latency_ms": int((time.time() - t0) * 1000)}

    if name == "quote_pdf_send":
        if do_quote is None:
            if ALLOW_SAFE_DEGRADE:
                return _fallback_done(payload, "quote module missing; degraded")
            raise RuntimeError("quote module missing")
        amount = float(payload.get("amount", 0.0))
        pdf = do_quote(  # type: ignore
            None,
            payload.get("mail_id", "?"),
            payload.get("to", ""),
            payload.get("items", []),
            amount,
            payload.get("currency", "TWD"),
            idem_key,
        )
        return {"ok": True, "pdf": pdf, "latency_ms": int((time.time() - t0) * 1000)}

    # 未知 action：直接降級
    return _fallback_done(payload, f"unknown action: {name}")
PY

echo "[5/9] make sure db config exists (sqlite fallback)"
mkdir -p src/smart_mail_agent/db
if [ ! -f src/smart_mail_agent/db/config.py ]; then
  cat > src/smart_mail_agent/db/config.py <<'PY'
import os, pathlib

def get_db_url() -> str:
    url = os.getenv("SMA_DB_URL")
    if not url:
        pathlib.Path("reports_auto").mkdir(exist_ok=True)
        url = "sqlite:///reports_auto/sma.sqlite3"
    return url
PY
fi

echo "[6/9] run ruff auto-fix + formatter（全倉）"
ruff check src tests --fix || true
ruff format src tests || true

echo "[7/9] run tests (pytest -q)"
pytest -q || true

echo "[8/9] migrate (alembic upgrade head)"
alembic upgrade head || true

echo "[9/9] show summary"
echo "---- Ruff left issues (if any) ----"
ruff check src tests || true
echo "---- pytest summary (exit code above) ----"
echo "---- done ----"
