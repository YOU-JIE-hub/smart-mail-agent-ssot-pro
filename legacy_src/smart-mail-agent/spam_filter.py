# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Sequence


class SpamFilterOrchestrator:
    def is_legit(
        self,
        *,
        subject: str = "",
        content: str = "",
        sender: str = "",
        to: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        text = f"{subject} {content}"
        reasons: List[str] = []

        # 粗略關鍵字偵測
        for kw in ("免費", "中獎", "贈品"):
            if kw in text:
                reasons.append("zh_keywords")
                break

        # 群發偵測
        if to and len(list(to)) >= 3:
            reasons.append("bulk")

        is_spam = bool(reasons)
        return {"allow": (not is_spam), "is_spam": is_spam, "reasons": reasons}
