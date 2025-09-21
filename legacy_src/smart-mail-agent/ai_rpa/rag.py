__all__=["build_index","query"]
def build_index(*a, **k): return {"ok": True, "docs": 0}
def query(q:str, **k): return {"answer": "offline-rag-stub", "chunks": []}
