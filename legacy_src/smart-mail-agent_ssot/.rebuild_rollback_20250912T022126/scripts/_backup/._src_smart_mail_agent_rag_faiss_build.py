from __future__ import annotations

from pathlib import Path
from typing import Any

# 第三方匯入：先 langchain.* 再 langchain_community.*（滿足 Ruff I001）
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
    from langchain_community.document_loaders import TextLoader  # type: ignore
    from langchain_community.vectorstores import FAISS  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(f"[rag/faiss_build] Missing langchain community packages: {e}") from e

from .provider import HashEmb

ROOT = Path(".").resolve()
KB_DIR = ROOT / "kb_docs"
OUT = ROOT / "reports_auto" / "kb" / "faiss_index"


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    if not KB_DIR.exists():
        return {"built": 0, "index": str(OUT), "ok": True}

    texts = []
    for p in KB_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".txt", ".md"):
            texts.append(TextLoader(str(p), encoding="utf-8").load()[0])

    if not texts:
        return {"built": 0, "index": str(OUT), "ok": True}

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs: list[Any] = []
    for d in texts:
        docs += splitter.split_documents([d])

    emb = HashEmb()  # 離線 embeddings
    vs = FAISS.from_documents(docs, emb)
    vs.save_local(OUT, index_name="kb")
    return {"built": len(docs), "index": str(OUT), "ok": True}


if __name__ == "__main__":
    import json

    print(json.dumps(build(), ensure_ascii=False))
