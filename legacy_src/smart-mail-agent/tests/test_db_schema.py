import os, sqlite3, re
def test_db_schema_tables_and_no_when_reserved():
    assert os.path.exists("db/sma.sqlite"), "db missing"
    con = sqlite3.connect("db/sma.sqlite"); cur = con.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    rows = cur.fetchall(); names = {r[0] for r in rows}
    assert {"actions","intent_preds","kie_spans","err_log"}.issubset(names)
    sql_all = " ".join((r[1] or "") for r in rows).lower()
    assert " create table errors " not in sql_all
    assert "err_log" in sql_all
