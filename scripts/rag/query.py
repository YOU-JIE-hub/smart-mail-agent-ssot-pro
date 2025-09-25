import sqlite3, sys, json, re
from scripts.obs.audit import audit_rag
from scripts.llm.gateway import summarize

# 簡單同義詞表（可加）
SYN = {
    "理賠": ["理賠","理赔","賠償","賠付"],
    "文件": ["文件","資料","材料","證明","單據","收據"],
    "需要": ["需要","所需","須","必備"]
}

def normalize(q:str)->str:
    # 去除標點、空白，保留中英數
    return re.sub(r"[^\w\u4e00-\u9fff]+", " ", q).strip()

def expand_keywords(q:str):
    base = normalize(q).split()
    # 若沒有分詞（多為中文短句），用抽取高價值詞
    if not base:
        base = list(q)
    out=set()
    for t in base:
        if t in SYN:
            out |= set(SYN[t])
        else:
            out.add(t)
    # 常見組合：理賠、文件、需要
    for k in ["理賠","文件","需要"]:
        out |= set(SYN.get(k,[k]))
    return [w for w in out if w.strip()]

def _fts5(con, terms, k):
    # 將關鍵詞轉成 FTS OR 查詢
    if not terms: return []
    query = " OR ".join(terms)
    try:
        cur=con.execute("SELECT doc, path, content FROM chunks WHERE chunks MATCH ? LIMIT ?", (query, k))
        return [{"doc":r[0],"path":r[1],"content":r[2]} for r in cur.fetchall()]
    except Exception:
        return []

def _like(con, terms, k):
    if not terms: return []
    # 用 OR 組合：content LIKE %詞% OR %詞2%
    clauses = " OR ".join(["content LIKE ?"]*len(terms))
    args = [f"%{t}%" for t in terms]
    cur=con.execute(f"SELECT doc, path, content FROM chunks WHERE {clauses} LIMIT ?", (*args, k))
    return [{"doc":r[0],"path":r[1],"content":r[2]} for r in cur.fetchall()]

def search(q, db="db/rag_index.sqlite", k=5):
    con=sqlite3.connect(db)
    terms = expand_keywords(q)
    rows=_fts5(con, terms, k)
    if not rows: rows=_like(con, terms, k)
    con.close()
    return rows

def answer(question, k=5):
    hits=search(question, k=k)
    ctx="\n\n".join(f"[{i}] ({h['doc']}) {h['content']}" for i,h in enumerate(hits))
    prompt=f"根據下列『來源片段』回答問題；若無依據則明確說不知道：\n問題：{question}\n來源：\n{ctx}\n"
    out=summarize("policy_qa", prompt, task="rag_synthesis")
    cites=[{"doc":h["doc"],"path":h["path"]} for h in hits]
    retr="fts5" if hits else "like"
    audit_rag(question, out, cites, retriever=retr, k=k)
    print(out); print("\nCITATIONS:", json.dumps(cites, ensure_ascii=False))

if __name__=="__main__":
    q=" ".join(sys.argv[1:]) or "理賠需要哪些文件"
    answer(q)
