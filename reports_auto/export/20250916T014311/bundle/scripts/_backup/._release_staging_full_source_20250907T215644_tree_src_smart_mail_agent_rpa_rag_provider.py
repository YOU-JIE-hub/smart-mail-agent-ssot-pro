from __future__ import annotations


class RuleRAG:
    def __init__(self, rules: dict[str, str] | None = None) -> None:
        self.rules = rules or {}

    def query(self, query: str | None) -> dict[str, object]:
        txt = ""
        hits = 0
        for k, v in self.rules.items():
            if k in (query or ""):
                txt += f"- {v}\n"
                hits += 1
        if not txt:
            txt = "已收到您的問題，將由客服盡快回覆（離線回退）。"
        return {"ok": True, "answer": txt.strip(), "hits": hits}
