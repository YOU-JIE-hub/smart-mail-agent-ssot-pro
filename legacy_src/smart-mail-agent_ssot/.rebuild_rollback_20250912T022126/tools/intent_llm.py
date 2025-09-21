from __future__ import annotations
import os, time, json, sqlite3, uuid
from pathlib import Path

def _names():
    p=Path("artifacts_prod/intent_names.json")
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))["names"]
        except Exception: pass
    # fallback：白名單
    p2=Path("configs/intent_names_override.txt")
    if p2.exists():
        return [ln.strip() for ln in p2.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return ["一般回覆"]

def _ensure_llm_table(db="db/sma.sqlite"):
    con=sqlite3.connect(db); cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS llm_calls(
        ts TEXT, model TEXT, intent TEXT, prompt_tokens INT, completion_tokens INT,
        latency_ms INT, cost_usd REAL, request_id TEXT, ok INT, note TEXT
    )""")
    con.commit(); con.close()

def classify(subject:str, body:str)->str:
    # 沒有 OPENAI_API_KEY 就直接回退「一般回覆」，並寫審計一筆 note
    _ensure_llm_table()
    names=_names()
    api=os.getenv("OPENAI_API_KEY")
    ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not api:
        con=sqlite3.connect("db/sma.sqlite"); cur=con.cursor()
        cur.execute("INSERT INTO llm_calls(ts, model, intent, prompt_tokens, completion_tokens, latency_ms, cost_usd, request_id, ok, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (ts,"-", "一般回覆", 0,0,0,0.0, str(uuid.uuid4()), 1, "llm_disabled"))
        con.commit(); con.close()
        return "一般回覆"
    try:
        from openai import OpenAI
        t0=time.time()
        cli=OpenAI(api_key=api)
        sys="你是郵件路由器，只能從候選清單選一個最符合的意圖輸出（只輸出意圖文字）。"
        user=f"候選：{names}\nSubject:{subject}\nBody:{(body or '')[:800]}"
        resp=cli.chat.completions.create(model=os.getenv("SMA_LLM_MODEL","gpt-4o-mini"),
                                         messages=[{"role":"system","content":sys},
                                                   {"role":"user","content":user}],
                                         temperature=0)
        choice=(resp.choices[0].message.content or "").strip()
        latency=int((time.time()-t0)*1000)
        con=sqlite3.connect("db/sma.sqlite"); cur=con.cursor()
        cur.execute("INSERT INTO llm_calls(ts, model, intent, prompt_tokens, completion_tokens, latency_ms, cost_usd, request_id, ok, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (ts, os.getenv("SMA_LLM_MODEL","gpt-4o-mini"), choice, getattr(resp.usage,'prompt_tokens',0), getattr(resp.usage,'completion_tokens',0),
             latency, 0.0, getattr(resp,'id',str(uuid.uuid4())), 1, "ok"))
        con.commit(); con.close()
        return choice if choice in names else "一般回覆"
    except Exception as e:
        con=sqlite3.connect("db/sma.sqlite"); cur=con.cursor()
        cur.execute("INSERT INTO llm_calls(ts, model, intent, prompt_tokens, completion_tokens, latency_ms, cost_usd, request_id, ok, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (ts,"-", "一般回覆", 0,0,0,0.0, str(uuid.uuid4()), 0, f"err:{type(e).__name__}"))
        con.commit(); con.close()
        return "一般回覆"
