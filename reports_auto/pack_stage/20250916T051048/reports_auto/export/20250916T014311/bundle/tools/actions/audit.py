from __future__ import annotations
import sqlite3, pathlib, time, json, hashlib
DB = pathlib.Path("db/sma.sqlite"); DB.parent.mkdir(parents=True, exist_ok=True)

def _con():
    con=sqlite3.connect(DB); con.execute("PRAGMA journal_mode=WAL;"); return con

def migrate():
    con=_con()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS actions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, mail_id TEXT, intent TEXT, action TEXT,
      hash TEXT UNIQUE, status TEXT, artifact_path TEXT, external_ref TEXT, error TEXT, latency_ms REAL
    );
    CREATE TABLE IF NOT EXISTS events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, kind TEXT, payload TEXT
    );
    CREATE TABLE IF NOT EXISTS dead_letters(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, mail_id TEXT, intent TEXT, action TEXT, hash TEXT, error TEXT, payload TEXT
    );
    """)
    con.commit(); con.close()

def action_hash(mail_id:str, intent:str, action:str, params:dict)->str:
    s=json.dumps({"mail_id":mail_id,"intent":intent,"action":action,"params":params}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def already_done(h:str)->bool:
    con=_con(); cur=con.cursor()
    cur.execute("SELECT 1 FROM actions WHERE hash=? AND status='ok' LIMIT 1", (h,))
    row=cur.fetchone(); con.close()
    return bool(row)

def record(**k):
    con=_con()
    con.execute("INSERT OR REPLACE INTO actions(ts,mail_id,intent,action,hash,status,artifact_path,external_ref,error,latency_ms) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (k.get("ts"),k.get("mail_id"),k.get("intent"),k.get("action"),k.get("hash"),k.get("status"),
                 k.get("artifact_path"),k.get("external_ref"),k.get("error"),k.get("latency_ms")))
    con.commit(); con.close()

def event(kind:str, payload:dict):
    con=_con(); con.execute("INSERT INTO events(ts,kind,payload) VALUES(?,?,?)",(time.strftime("%Y-%m-%dT%H:%M:%S"), kind, json.dumps(payload, ensure_ascii=False))); con.commit(); con.close()

def dead_letter(**k):
    con=_con()
    con.execute("INSERT INTO dead_letters(ts,mail_id,intent,action,hash,error,payload) VALUES(?,?,?,?,?,?,?)",
                (time.strftime("%Y-%m-%dT%H:%M:%S"), k.get("mail_id"), k.get("intent"), k.get("action"),
                 k.get("hash"), k.get("error"), json.dumps(k.get("payload") or {}, ensure_ascii=False)))
    con.commit(); con.close()
