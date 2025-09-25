from __future__ import annotations
import sqlite3, argparse

SCHEMA = [
    ("ts", "TEXT"),
    ("model", "TEXT"),
    ("intent", "TEXT"),
    ("prompt_tokens", "INTEGER"),
    ("completion_tokens", "INTEGER"),
    ("latency_ms", "INTEGER"),
    ("cost_usd", "REAL"),
    ("request_id", "TEXT"),
    ("ok", "INTEGER"),
    ("note", "TEXT"),
]

def ensure_schema(db:str):
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_calls'")
    exists = cur.fetchone() is not None
    if not exists:
        cols = ", ".join([f"{k} {t}" for k,t in SCHEMA])
        cur.execute(f"CREATE TABLE llm_calls ({cols})")
    else:
        cur.execute("PRAGMA table_info('llm_calls')")
        have = {row[1] for row in cur.fetchall()}  # row[1]=name
        for k,t in SCHEMA:
            if k not in have:
                cur.execute(f"ALTER TABLE llm_calls ADD COLUMN {k} {t}")
    con.commit()
    con.close()
    print(f"[MIGRATE] llm_calls schema OK -> {db}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    args = ap.parse_args()
    ensure_schema(args.db)
