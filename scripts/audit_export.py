import sqlite3, csv, time
from pathlib import Path

ROOT = Path.cwd()
DB   = ROOT/"reports_auto/audit/audit.sqlite"
OUTD = ROOT/f"reports_auto/audit/export_{time.strftime('%Y%m%dT%H%M%S')}"
OUTD.mkdir(parents=True, exist_ok=True)

def dump_table(conn, table):
    p = OUTD/f"{table}.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        cur = conn.cursor()
        rows = cur.execute(f"SELECT * FROM {table}").fetchall()
        cols = [d[0] for d in cur.description]
        csv.writer(f).writerow(cols)
        csv.writer(f).writerows(rows)
    return p

def main():
    if not DB.exists():
        print("[FATAL] DB not found:", DB); return 2
    conn = sqlite3.connect(DB)
    paths = [dump_table(conn, t) for t in ("runs","actions","artifacts")]

    # 簡易彙總 markdown
    cur = conn.cursor()
    total_actions = cur.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    by_act = cur.execute("SELECT action, COUNT(*) FROM actions GROUP BY action ORDER BY 2 DESC").fetchall()

    md = OUTD/"report.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# RPA 審計報告\n\n")
        f.write(f"- 匯出時間：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- actions 總數：{total_actions}\n\n")
        f.write("## 依動作統計\n\n")
        for a,cnt in by_act:
            f.write(f"- {a}: {cnt}\n")
        f.write("\n> 明細：runs.csv / actions.csv / artifacts.csv\n")
    conn.close()

    print("[OK] export dir ->", OUTD)
    for p in [*paths, md]: print(" -", p)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
