#!/usr/bin/env python3
import os, sqlite3, time, hashlib, sys
from pathlib import Path

PROJ = Path(".").resolve()
DB_TARGET = Path(os.environ.get("SMA_DB_PATH", "db/sma.sqlite"))
STATUS_DIR = PROJ / "reports_auto" / "status"
STATUS_DIR.mkdir(parents=True, exist_ok=True)

TABLE_SPECS = {
    "mails": [
        ("case_id", "TEXT"),
        ("run_ts", "TEXT"),
        ("subject", "TEXT"),
        ("from_addr", "TEXT"),
        ("to_addr", "TEXT"),
        ("received_at", "TEXT"),
        ("summary_json", "TEXT"),
    ],
    "intent_preds": [
        ("case_id","TEXT"),("label","TEXT"),("score","REAL"),("threshold","REAL"),("run_ts","TEXT"),
    ],
    "kie_spans": [
        ("case_id","TEXT"),("field","TEXT"),("value","TEXT"),("start","INT"),("end","INT"),("engine","TEXT"),("run_ts","TEXT"),
    ],
    "actions": [
        ("case_id","TEXT"),("intent","TEXT"),("action_type","TEXT"),("status","TEXT"),
        ("payload_ref","TEXT"),("idempotency_key","TEXT"),
        ("started_at","TEXT"),("ended_at","TEXT"),
        ("decision_aid_json","TEXT"),("run_ts","TEXT"),
    ],
    "approvals": [
        ("case_id","TEXT"),("field","TEXT"),("old_value","TEXT"),("new_value","TEXT"),
        ("decision","TEXT"),("approver","TEXT"),("approved_at","TEXT"),("run_ts","TEXT"),
    ],
    "err_log": [
        ("case_id","TEXT"),("stage","TEXT"),("message","TEXT"),("detail","TEXT"),("run_ts","TEXT"),
    ],
    "metrics": [
        ("name","TEXT"),("value","REAL"),("unit","TEXT"),("run_ts","TEXT"),
    ],
    "llm_calls": [
        ("request_id","TEXT"),("model","TEXT"),("input_tokens","INT"),("output_tokens","INT"),
        ("cost_estimate","REAL"),("cache_key","TEXT"),("cache_hit","INT"),
        ("latency_ms","INT"),("status","TEXT"),("schema_name","TEXT"),("run_ts","TEXT"),
    ],
}

VIEWS = {
    "v_actions_summary": """
        CREATE VIEW v_actions_summary AS
        SELECT run_ts, intent, action_type,
               SUM(CASE WHEN status='succeeded' THEN 1 ELSE 0 END) as succ,
               SUM(CASE WHEN status='downgraded' THEN 1 ELSE 0 END) as downgraded,
               SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
               COUNT(1) as total
        FROM actions GROUP BY run_ts, intent, action_type
    """,
    "v_sla_queue": """
        CREATE VIEW v_sla_queue AS
        SELECT a.case_id, a.field, a.old_value, a.new_value, a.decision, a.approver, a.approved_at, a.run_ts
        FROM approvals a WHERE a.field='sla' AND (a.decision IS NULL OR a.decision='')
    """,
    "v_latency_ms": """
        CREATE VIEW v_latency_ms AS
        SELECT case_id, action_type,
               CAST((strftime('%s', COALESCE(ended_at, started_at)) - strftime('%s', started_at)) * 1000 AS INT) AS latency_ms,
               run_ts FROM actions WHERE started_at IS NOT NULL
    """,
    "v_llm_cost_daily": """
        CREATE VIEW v_llm_cost_daily AS
        SELECT substr(run_ts,1,10) AS day, model,
               SUM(COALESCE(cost_estimate,0)) AS est_cost,
               SUM(COALESCE(cache_hit,0)) AS cache_hits,
               COUNT(1) AS calls
        FROM llm_calls GROUP BY day, model
    """,
}

def ensure_db():
    DB_TARGET.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_TARGET))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=OFF;")  # 便於增列

    report = {"target": str(DB_TARGET), "tables": {}, "added_columns": {}, "created_tables": [], "indexes": []}

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {r[0] for r in cur.fetchall()}

    # 1) 建表或補欄位（不破壞既有資料）
    for tname, cols in TABLE_SPECS.items():
        if tname not in existing_tables:
            # 建立最小表
            cols_sql = ", ".join([f"{c} {typ}" for c, typ in cols])
            conn.execute(f"CREATE TABLE {tname} ({cols_sql});")
            report["created_tables"].append(tname)
        else:
            # 確認欄位，缺的就 ADD COLUMN
            cur.execute(f"PRAGMA table_info({tname})")
            have = {r[1] for r in cur.fetchall()}
            added = []
            for c, typ in cols:
                if c not in have:
                    conn.execute(f"ALTER TABLE {tname} ADD COLUMN {c} {typ}")
                    added.append(c)
            if added:
                report["added_columns"][tname] = added

    # 2) 索引（避免 REPLACE 行為依賴 PK）：用 UNIQUE INDEX 保障 case_id 不重複
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mails_case_id ON mails(case_id)")
        report["indexes"].append("idx_mails_case_id")
    except sqlite3.DatabaseError:
        pass

    conn.commit()

    # 3) 視圖（先刪再建，確保最新）
    for vname, vsql in VIEWS.items():
        try:
            conn.execute(f"DROP VIEW IF EXISTS {vname}")
            conn.execute(vsql)
        except sqlite3.DatabaseError:
            pass
    conn.commit()
    conn.close()

    ts = time.strftime("%Y%m%dT%H%M%S")
    out = STATUS_DIR / f"DB_MIGRATE_{ts}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# DB Migration Report {ts}\n\n- target: `{report['target']}`\n")
        if report["created_tables"]:
            f.write("\n- created_tables:\n")
            for t in report["created_tables"]: f.write(f"  - {t}\n")
        if report["added_columns"]:
            f.write("\n- added_columns:\n")
            for t, cols in report["added_columns"].items():
                f.write(f"  - {t}: {', '.join(cols)}\n")
        if report["indexes"]:
            f.write("\n- indexes:\n")
            for ix in report["indexes"]: f.write(f"  - {ix}\n")
    print(f"[OK] DB migration/repair done. Report => {out}")

if __name__ == "__main__":
    ensure_db()
