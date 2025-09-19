import argparse
import json
import os

from smart_mail_agent.rag.compat import FAISS
from smart_mail_agent.rag.provider import HashEmb
from smart_mail_agent.utils.config import OPENAI_KEY, SMA_KB_INDEX_NAME, paths


def _md(s: str) -> str:
    return s.replace("<", "&lt;").replace(">", "&gt;")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    q = args.question or "付款條件是什麼？"
    P = paths()
    name = os.getenv(SMA_KB_INDEX_NAME, "kb")
    idx = P.kb_index
    if not (idx / f"{name}.faiss").exists() and (idx / "index.faiss").exists():
        name = "index"
    if os.getenv(OPENAI_KEY):
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # type: ignore

        emb = OpenAIEmbeddings(model="text-embedding-3-small")
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    else:
        emb = HashEmb()
        llm = None
    vs = FAISS.load_local(idx, embeddings=emb, index_name=name, allow_dangerous_deserialization=True)
    docs = vs.similarity_search(q, k=args.k)
    sources = "\n".join(
        [f"- `{d.metadata.get('source')}` | {_md(' '.join((d.page_content or '').splitlines())[:220])}" for d in docs]
    )
    answer = "（離線）依檢索片段整理：\n- 重點1…\n- 重點2…\n\n建議：請參照來源片段列表。"
    if llm:
        ctx = "\n\n".join([d.page_content for d in docs])
        prompt = f"根據下列文件片段回答問題，務必引用條款並簡潔：\n\n問題：{q}\n\n文件片段：\n{ctx}\n\n回答："
        answer = llm.invoke(prompt).content.strip()  # type: ignore
    out = (P.status / f"RAG_QA_{name}.md") if not args.out else args.out
    open(out, "w", encoding="utf-8").write(
        f"# RAG QA\n\n**問題**：{q}\n\n**回答**：\n\n{_md(answer)}\n\n---\n**來源片段**：\n\n{sources}\n"
    )
    print(json.dumps({"ok": True, "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
