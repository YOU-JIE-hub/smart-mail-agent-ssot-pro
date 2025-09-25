from __future__ import annotations

import json

from smart_mail_agent.rag.faiss_build import build


def main() -> int:
    res = build()
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 0  # 沒 KB 也不當錯


if __name__ == "__main__":
    raise SystemExit(main())
