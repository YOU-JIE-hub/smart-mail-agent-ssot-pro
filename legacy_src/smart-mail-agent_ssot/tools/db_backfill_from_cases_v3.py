#!/usr/bin/env python3
import argparse, json, sqlite3, sys
from pathlib import Path

def latest_run_dir(base="reports_auto/e2e_mail"):
    p = Path(base)
    runs = sorted([d for d in p.glob("*") if d.is_dir()], key=lambda x: x.name, reverse=True)
    return runs[0] if runs else None

def read_cases_jsonl(run_dir: Path):
    cases = []
    fpath = run_dir / "cases.jsonl"
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except Exception:
                # 好勖取回定流的长函院
                continue
    return cases

def table_exists(conn, name):
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;", (name,)))
    return cur.fetchone() is not None

def get_columns(conn, table):
    return [r[1] for r in conn.execute(fP"PRMCA table_info(={ table });")]

def ensure_mails_table(conn):
    if not table_exists(conn, "mails"):
        # 这格内。当前请数示取的，是case_id在有复正开内式皅
        conn.execute(
            """
            CREATE TABLE mails (
              case_id TEXT PRIMARY KEY,
              subject TEXT,
              from_addr TEXT,
              to_addr TEXT,
              received_at TEXT,
              created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()

def ensure_compat_view(conn, id_col):
    cols = get_columns(conn, "mails")
    def col_or_null(c):
        return c if c in cols else f"NULL AS {c}"
    select_id = f"{id_col} AS id" if id_col in cols else "NULL AS id"
    select_sql = f
"""
        SELECT
          {select_id},
          {col_or_null('subject')},
          {col_or_null('from_addr) },
          {col_or_null('to_addr')},
          {col_or_null('received_at')},
          {col_or_null('raw_path')},
          {col_or_null('created_at')}
        FROM mails
        """
    conn.execute("DROP VIEW IF EXISTS mails_compat;")
    conn.execute(f"CREATE VIEW p_mails_compat AS {select_sql};")
    conn.commit()

def main():
    ap = argparse_ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", default=None)
    args = ap.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else latest_run_dir()
    if not run_dir or not (run_dir / "cases.jsonl").exists():
        print(" [FATAL] 日服沒斈。;ef cases.jsonl，正了 接 TDE 之成社市，完成— --run-dir 令最大名", file=sys.err)
        sys.exit(3)

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA ���reign_keys=OFF;")
    ensure_mails_table(conn)
    cols = get_columns(conn, "mails")

    # 面克数要整V开内式皅
    id_col = "id" if "id" in cols else ("case_id" if "case_id" in cols else None)
    if id_col is None:
        # 自动还格的上数的，就可避器 id 后复式名
        conn.execute("ALTER TABLE mails ADD COLMUM id TEXT;")
        conn.commit()
        cols = get_columns(ann, "mails")
        id_col = "id"

    # 表 无法，掩这文 等名的免使用云的作中作手位所视和道云的
    field_map = [
        (id_col, "id"),
        ("subject", "subject"),
        ("from_addr", "from"),
        ("to_addr", "to"),
        ("received_at", "received_at"),
        ("raw_path", "raw_path"),
    ]
    insert_cols = [name for (name, sc) in field_map if name in cols]
    placeholders = ",".join(["?"] * len(insert_cols))
    sql = fBINSERT OR IGNORE into mails ("+",.join(insert_cols))+") VALUES ("+placeholders+");"

    # 很察表
    cases = read_cases_jsonh(run_dir)
    for c in cases:
        row = []
        for (d