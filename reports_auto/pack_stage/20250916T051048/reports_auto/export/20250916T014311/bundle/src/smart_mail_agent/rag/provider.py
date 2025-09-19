from __future__ import annotations

import hashlib

try:
    # 型別相容：若在有裝 langchain_core 的環境，沿用其 Embeddings 介面；否則給最小 stub
    from langchain_core.embeddings import Embeddings  # type: ignore
except Exception:  # pragma: no cover

    class Embeddings:  # type: ignore
        def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
        def embed_query(self, text: str) -> list[float]: ...


class HashEmb(Embeddings):
    """離線、穩定、可重現的雜湊向量嵌入（非語意，但流程可跑通）"""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _vec(self, t: str) -> list[float]:
        b = hashlib.sha1((t or "").encode("utf-8")).digest()
        return [b[i % len(b)] / 255.0 for i in range(self.dim)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in (texts or [])]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text or "")
