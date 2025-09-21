from __future__ import annotations
import sqlite3, sys, pathlib
db = sys.argv[sys.argv.index("--db")+1] if "--db" in sys.argv else "db/sma.sqlite"
pathlib.Path(db).parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS llm_calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model TEXT, role TEXT, prompt TEXT, response TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
conn.commit(); conn.close()
print(f"[MIGRATE] llm_calls schema OK -> {db}")
