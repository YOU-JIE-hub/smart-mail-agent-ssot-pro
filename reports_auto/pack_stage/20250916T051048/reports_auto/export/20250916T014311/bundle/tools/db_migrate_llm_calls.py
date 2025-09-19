from __future__ import annotations
import sqlite3, pathlib
db = pathlib.Path("db/sma.sqlite"); db.parent.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(db); cur = con.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS llm_calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_ts TEXT, model TEXT, prompt TEXT, response TEXT, created_at TEXT
)""")
con.commit(); con.close()
print(f"[MIGRATE] llm_calls schema OK -> {db}")
