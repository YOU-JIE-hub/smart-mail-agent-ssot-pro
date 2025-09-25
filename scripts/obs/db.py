import os, sqlite3, pathlib, contextlib, time, json
from urllib.parse import urlparse

DB_URL=os.getenv("DB_URL","sqlite:///db/sma.sqlite")

def _ensure_parent(p): pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)

def connect():
    u=urlparse(DB_URL)
    if u.scheme.startswith("sqlite"):
        path = u.path or "/db/sma.sqlite"
        if path.startswith("/"): path=path[1:]
        _ensure_parent(path)
        return sqlite3.connect(path, check_same_thread=False)
    import psycopg2
    return psycopg2.connect(DB_URL)

SCHEMA="""
CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  intent TEXT,
  action TEXT
);
CREATE TABLE IF NOT EXISTS llm_traces(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  intent TEXT,
  task TEXT,
  prompt TEXT,
  output TEXT,
  provider TEXT
);
CREATE TABLE IF NOT EXISTS rag_queries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  question TEXT,
  answer TEXT
);
"""

# 需要補齊的欄位（若不存在就 ALTER TABLE ADD COLUMN）
REQUIRED = {
  "actions": [
    ("payload_json","TEXT"),
    ("idempotency_key","TEXT"),
    ("status","TEXT")
  ],
  "llm_traces": [
    ("usage_json","TEXT")
  ],
  "rag_queries": [
    ("citations_json","TEXT"),
    ("retriever","TEXT"),
    ("k","INTEGER")
  ],
}

def _table_columns(con, table):
    cols = set()
    try:
        for _, name, typ, *_ in con.execute(f"PRAGMA table_info({table})"):
            cols.add(name)
    except Exception:
        pass
    return cols

def migrate():
    with contextlib.closing(connect()) as c:
        # 先確保基本表存在
        c.executescript(SCHEMA)
        # 逐表補欄位
        for tbl, need in REQUIRED.items():
            have = _table_columns(c, tbl)
            for col, typ in need:
                if col not in have:
                    c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
        c.commit()

def init():
    # init = create + migrate
    migrate()

def insert(table, **cols):
    with contextlib.closing(connect()) as c:
        ks=",".join(cols); qs=",".join(["?"]*len(cols))
        c.execute(f"INSERT INTO {table} ({ks}) VALUES ({qs})", tuple(cols.values()))
        c.commit()

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
