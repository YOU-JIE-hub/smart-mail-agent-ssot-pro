from __future__ import annotations

import re
from pathlib import Path

import yaml  # type: ignore


def answer_policy_question(q: str) -> str:
    kb = Path("policies") / "rules.yaml"
    if kb.exists():
        data = yaml.safe_load(kb.read_text(encoding="utf-8")) or {}
        best_text = ""
        best_score = 0
        for _k, v in data.items():
            score = len(set(re.findall(r"\w+", q.lower())) & set(re.findall(r"\w+", str(v).lower())))
            if score > best_score:
                best_text = str(v)
                best_score = score
        if best_score > 0:
            return best_text
    return "我們已收到您的問題，以下為常見規則摘要：..."
