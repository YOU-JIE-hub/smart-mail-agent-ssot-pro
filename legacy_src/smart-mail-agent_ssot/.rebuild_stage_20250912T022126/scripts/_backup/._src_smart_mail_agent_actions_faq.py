from __future__ import annotations

import os
from typing import Any

from smart_mail_agent.rag.provider import HashEmb
from smart_mail_agent.utils.config import SMA_KB_INDEX_NAME, paths

try:
    from langchain_community.vectorstores import FAISS  # type: ignore
except Exception:  # pragma: no cover
    FAISS = None  # type: ignore


def _preview(txt: str, n: int = 80) -> str:
    return " ".join((txt or "").splitlines())[:n]


def run_faq(question: str) -> dict[str, Any]:
    p = paths()
    name = os.getenv(SMA_KB_INDEX_NAME, "kb")
    idx = p.kb_index
    if not (idx / f"{name}.faiss").exists() and (idx / "index.faiss").exists():
        name = "index"
    if FAISS is None:
        body = (
            f"問題：{question}\n\n"
            "建議回覆（離線模板）：\n"
            "- 付款方式：匯款/信用卡/對公轉帳\n"
            "- 出貨時間：接單後 3–5 工作天\n"
            "- 其他條款：請參見附件或官網\n"
        )
        art = p.status / "answers"
        art.mkdir(exist_ok=True)
        fn = art / f"answer_faq_{name}.md"
        fn.write_text(body, encoding="utf-8")
        return {"ok": True, "answer_path": str(fn), "sources": []}
    emb = HashEmb()
    vs = FAISS.load_local(idx, embeddings=emb, index_name=name, allow_dangerous_deserialization=True)  # type: ignore[arg-type]
    docs = vs.similarity_search(question, k=4)
    sources = [f"- {d.metadata.get('source')}: {_preview(d.page_content)}" for d in docs]
    body = (
        f"問題：{question}\n\n"
        "建議回覆（離線模板）：\n"
        "- 付款方式：匯款/信用卡/對公轉帳\n"
        "- 出貨時間：接單後 3–5 工作天\n"
        "- 其他條款：請參見附件或官網\n\n"
        "參考來源：\n" + "\n".join(sources)
    )
    art = p.status / "answers"
    art.mkdir(exist_ok=True)
    fn = art / f"answer_faq_{name}.md"
    fn.write_text(body, encoding="utf-8")
    return {"ok": True, "answer_path": str(fn), "sources": sources}
