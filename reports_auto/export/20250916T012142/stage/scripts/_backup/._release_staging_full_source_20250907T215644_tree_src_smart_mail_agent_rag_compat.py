from __future__ import annotations

try:
    from langchain.text_splitter import (  # type: ignore  # noqa: F401
        RecursiveCharacterTextSplitter,
    )
except Exception:
    from langchain.text_splitters import (  # type: ignore  # noqa: F401
        RecursiveCharacterTextSplitter,
    )

try:
    from langchain_community.vectorstores import FAISS  # type: ignore  # noqa: F401
except Exception:
    from langchain.vectorstores import FAISS  # type: ignore  # noqa: F401
