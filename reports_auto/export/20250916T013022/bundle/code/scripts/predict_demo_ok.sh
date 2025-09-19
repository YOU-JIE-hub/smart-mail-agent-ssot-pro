#!/usr/bin/env bash
# 穩定版 demo：.venv_clean、缺索引自動建、有金鑰用 OpenAI、沒金鑰用離線 HashEmb
set -u
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || true
. .venv_clean/bin/activate 2>/dev/null || true
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p reports_auto/{logs,status,kb/faiss_index} 2>/dev/null || true

TS="$(date +%Y%m%dT%H%M%S)"

echo "[1/3] 三模型冒煙 → reports_auto/status/SMOKE_${TS}.json"
python - <<'PY' >"reports_auto/status/SMOKE_${TS}.json" 2>"reports_auto/logs/smoke_err_${TS}.log" || true
import json
from smart_mail_agent.ml import infer
print(json.dumps(infer.smoke_all(), ensure_ascii=False, indent=2))
PY

echo "[2/3] RAG 建索引（缺就建） → reports_auto/logs/rag_build_${TS}.log"
python - <<'PY' >"reports_auto/logs/rag_build_${TS}.log" 2>&1 || true
import os, pathlib, json, hashlib
from typing import List

ROOT = pathlib.Path(".")
IDX = ROOT / "reports_auto/kb/faiss_index"
IDX.mkdir(parents=True, exist_ok=True)
INDEX_NAME = "kb"

# compat imports
try:
    from smart_mail_agent.rag.compat import RecursiveCharacterTextSplitter, FAISS
except Exception:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    try:
        from langchain_community.vectorstores import FAISS
    except Exception:
        from langchain.vectorstores import FAISS

USE_OPENAI = bool(os.getenv("OPENAI_API_KEY"))
if USE_OPENAI:
    from langchain_openai import OpenAIEmbeddings
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
else:
    class HashEmb:
        def _vec(self, t:str, d=384):
            b = hashlib.sha1((t or "").encode("utf-8")).digest()
            return [ b[i%len(b)]/255.0 for i in range(d) ]
        def embed_documents(self, texts:List[str]): return [ self._vec(t) for t in texts ]
        def embed_query(self, text:str): return self._vec(text)
    emb = HashEmb()

kb_faiss = IDX / f"{INDEX_NAME}.faiss"
kb_pkl   = IDX / f"{INDEX_NAME}.pkl"
if kb_faiss.exists() and kb_pkl.exists():
    print("index exists, skip build")
else:
    # minimal corpus from repo
    data_dir = ROOT / "reports_auto/kb/src"
    data_dir.mkdir(parents=True, exist_ok=True)
    if not any(data_dir.iterdir()):
        exts={".md",".txt",".py",".rst",".yaml",".yml"}
        for p in ROOT.rglob("*"):
            if p.suffix.lower() in exts and p.is_file() and p.stat().st_size<=256*1024:
                try:
                    data = p.read_text(encoding="utf-8", errors="ignore")[:20000]
                    (data_dir/p.name).write_text(data, encoding="utf-8")
                except Exception: pass
            if sum(1 for _ in data_dir.iterdir())>=40: break
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    texts, metas = [], []
    for f in sorted(data_dir.glob("*")):
        if not f.is_file(): continue
        try:
            raw = f.read_text(encoding="utf-8", errors="ignore")
        except Exception: continue
        chunks = splitter.split_text(raw)
        for i,ch in enumerate(chunks):
            texts.append(ch); metas.append({"source": str(f), "chunk": i})
    if texts:
        try:
            vs = FAISS.from_texts(texts=texts, embedding=emb, metadatas=metas)
        except TypeError:
            vs = FAISS.from_texts(texts, emb, metadatas=metas)
        vs.save_local(IDX, index_name=INDEX_NAME)
        print(f"built: {len(texts)} chunks")
    else:
        print("no texts; build skipped")

print("DONE")
PY

echo "[3/3] RAG 查詢 → reports_auto/logs/rag_query_${TS}.log"
python - <<'PY' >"reports_auto/logs/rag_query_${TS}.log" 2>&1 || true
import os, pathlib, json, hashlib
from typing import List
ROOT = pathlib.Path(".")
IDX = ROOT / "reports_auto/kb/faiss_index"
INDEX_NAME = "kb"

# compat
try:
    from smart_mail_agent.rag.compat import FAISS
except Exception:
    try:
        from langchain_community.vectorstores import FAISS
    except Exception:
        from langchain.vectorstores import FAISS

USE_OPENAI = bool(os.getenv("OPENAI_API_KEY"))
if USE_OPENAI:
    from langchain_openai import OpenAIEmbeddings
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
else:
    class HashEmb:
        def _v(self,t,d=384):
            b = hashlib.sha1((t or "").encode("utf-8")).digest()
            return [ b[i%len(b)]/255.0 for i in range(d) ]
        def embed_documents(self, texts:List[str]): return [ self._v(t) for t in texts ]
        def embed_query(self, text:str): return self._v(text)
    emb = HashEmb()

kb_faiss = IDX / f"{INDEX_NAME}.faiss"
kb_pkl   = IDX / f"{INDEX_NAME}.pkl"
if not (kb_faiss.exists() and kb_pkl.exists()):
    print("INDEX_MISSING: run build step first")
else:
    vs = FAISS.load_local(IDX, embeddings=emb, index_name=INDEX_NAME, allow_dangerous_deserialization=True)
    docs = vs.similarity_search("付款條件是什麼？", k=3)
    print(json.dumps([{"source": d.metadata.get("source"), "preview": d.page_content[:240]} for d in docs], ensure_ascii=False, indent=2))
print("DONE")
PY

echo "[OK] DEMO 完成；產物在 reports_auto/status 與 reports_auto/logs"
