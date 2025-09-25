import os, json, sqlite3, time, hashlib
from pathlib import Path

ROOT = Path.cwd()
LATEST = ROOT/"reports_auto/actions/latest"
DB = ROOT/"reports_auto/audit/audit.sqlite"
DB.parent.mkdir(parents=True, exist_ok=True)

def sha256_path(p: Path):
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def ensure_schema(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        root TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS actions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        mail TEXT NOT NULL,
        action TEXT NOT NULL,
        ok INTEGER NOT NULL,
        error TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS artifacts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_id INTEGER NOT NULL,
        kind TEXT,
        path TEXT,
        size INTEGER,
        sha256 TEXT,
        FOREIGN KEY(action_id) REFERENCES actions(id)
    )""")
    conn.commit()

def load_summary(root: Path):
    js = root/"actions_summary.json"
    if js.exists():
        return json.loads(js.read_text(encoding="utf-8"))
    # fallback：拼出一筆 handoff 也可
    return []

def main():
    if not LATEST.exists():
        print("[FATAL] latest not found:", LATEST); return 2
    conn = sqlite3.connect(DB)
    ensure_schema(conn)
    cur = conn.cursor()
    cur.execute("INSERT INTO runs(created_at, root) VALUES(?,?)", (time.strftime("%Y-%m-%d %H:%M:%S"), str(LATEST)))
    run_id = cur.lastrowid

    rows = load_summary(LATEST)
    for r in rows:
        cur.execute("INSERT INTO actions(run_id, mail, action, ok, error) VALUES(?,?,?,?,?)",
                    (run_id, r.get("mail",""), r.get("action",""), int(bool(r.get("ok",False))), r.get("error")))
        act_id = cur.lastrowid
        for art in (r.get("artifacts") or []):
            p = Path(art.get("path",""))
            size = p.stat().st_size if p.exists() else None
            cur.execute("INSERT INTO artifacts(action_id, kind, path, size, sha256) VALUES(?,?,?,?,?)",
                        (act_id, art.get("kind"), str(p), size, sha256_path(p) if p.exists() else None))
    conn.commit()
    conn.close()
    print(f"[OK] audit -> {DB}")

if __name__=="__main__":
    raise SystemExit(main())
