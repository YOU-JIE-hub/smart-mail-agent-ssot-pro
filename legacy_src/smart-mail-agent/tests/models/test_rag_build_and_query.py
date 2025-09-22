import os
from models.rag import build as rag_build
from models.rag import serving as rag_serv

def test_rag_build_and_local_search():
    idx = rag_build.build()
    res = rag_serv.search("退款 機制")
    assert res and res[0]["id"] in ("refund","invoice","limit")

def test_rag_gpt_fallback_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SMA_RAG_PROVIDER","gpt")
    res = rag_serv.answer("如何退款？", top_k=2)
    # 沒有 API KEY 時會 fallback 到 local
    assert res["provider"]=="local" and "passages" in res
