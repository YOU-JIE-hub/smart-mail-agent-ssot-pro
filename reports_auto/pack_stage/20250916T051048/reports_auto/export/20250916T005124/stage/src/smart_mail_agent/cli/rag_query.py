import argparse
import json
import os
import pathlib

from smart_mail_agent.rag.compat import FAISS
from smart_mail_agent.rag.provider import HashEmb
from smart_mail_agent.utils.config import OPENAI_KEY, SMA_KB_INDEX_NAME, paths


def _preview(txt: str, n: int = 160) -> str:
    return " ".join((txt or "").splitlines())[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?", default="付款條件是什麼？")
    ap.add_argument("--index", default=None)
    args = ap.parse_args()
    P = paths()
    idx = pathlib.Path(args.index) if args.index else P.kb_index
    idx.mkdir(parents=True, exist_ok=True)
    name = os.getenv(SMA_KB_INDEX_NAME, "kb")
    if not (idx / f"{name}.faiss").exists() and (idx / "index.faiss").exists():
        name = "index"
    emb = HashEmb()
    if os.getenv(OPENAI_KEY):
        try:
            from langchain_openai import OpenAIEmbeddings  # type: ignore

            emb = OpenAIEmbeddings(model="text-embedding-3-small")
        except Exception:
            pass
    vs = FAISS.load_local(idx, embeddings=emb, index_name=name, allow_dangerous_deserialization=True)
    docs = vs.similarity_search(args.question, k=4)
    lines = [f"- {d.metadata.get('source')}: {_preview(d.page_content)}" for d in docs]
    print(json.dumps({"kb_hits": len(docs), "index_name": name, "answer": "\n".join(lines)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
