from __future__ import annotations
import sqlite3, json
from pathlib import Path
db=Path("db/sma.sqlite"); out=Path("reports_auto/db_reports"); out.mkdir(parents=True, exist_ok=True)
con=sqlite3.connect(db); cur=con.cursor()
def dump(q,name):
    try:
        rows=cur.execute(q).fetchall()
        (out/name).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
        print("[DB]", name)
    except Exception as e:
        print("[DB][ERR]", name, e)
dump("SELECT * FROM v_intent_daily ORDER BY d DESC, intent;", Path("v_intent_daily.json"))
dump("SELECT * FROM v_action_stats ORDER BY n DESC;", Path("v_action_stats.json"))
dump("SELECT * FROM v_hitl_rate ORDER BY d DESC;", Path("v_hitl_rate.json"))
dump("SELECT * FROM v_kie_coverage ORDER BY d DESC;", Path("v_kie_coverage.json"))
