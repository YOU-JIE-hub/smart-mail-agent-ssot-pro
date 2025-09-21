from pathlib import Path
import sqlite3
from ai_rpa.actions_router import plan
from ai_rpa.actions_executor import Executor

def _count_rows(db_path, table):
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        cur.execute(f"SELECT COUNT(1) FROM {table}")
        return cur.fetchone()[0]
    finally:
        con.close()

def test_executor_dryrun_and_real_side_effects(tmp_path):
    text = "想洽談合作，請提供正式方案與報價"
    steps = plan(text)
    workdir = tmp_path/"work"; outbox = tmp_path/"outbox"; db = tmp_path/"db.sqlite"

    # dry-run：不落地
    ex = Executor(workdir, outbox, db, dry_run=True)
    res = ex.execute(steps, context={"qty":60, "email_to":"buyer@example.com", "meeting_title":"Intro"})
    assert any(r["result"].get("dry_run") for r in res)

    # real：會產出 email 與 pdf，並插入 DB（ticket/event/audit 至少 1 筆）
    ex2 = Executor(workdir, outbox, db, dry_run=False)
    res2 = ex2.execute(steps, context={"qty":5, "email_to":"buyer@example.com", "doc_data":{"title":"Quote"}})
    assert any(p.suffix==".eml" for p in outbox.iterdir())
    assert (workdir/"quote.pdf").exists()
    # DB 三表至少其中一表有資料（依 playbook 執行內容）
    assert (_count_rows(db,"tickets")+_count_rows(db,"events")+_count_rows(db,"audits")) >= 1
