#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/kie/infer.py
# 模組用途
#   KIE：若無 HF 權重則走 regex 後備。
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class KIE:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else Path(__file__).resolve().parents[3]
        self.hf: Path | None = None
        self.id2label: dict[int, str] = {}
        self._try_load_hf()

    def _try_load_hf(self) -> None:
        try:
            # 延遲匯入，若離線/無套件會直接走 regex 後備
            hfdir: Path | None = None
            if (self.root / "kie").exists():
                hfdir = self.root / "kie"
            elif (self.root / "reports_auto" / "kie" / "kie").exists():
                hfdir = self.root / "reports_auto" / "kie" / "kie"
            if hfdir and (hfdir / "config.json").exists():
                import json

                cfg = json.loads((hfdir / "config.json").read_text(encoding="utf-8"))
                id2label = cfg.get("id2label")
                if isinstance(id2label, dict):
                    id2label = {int(k): v for k, v in id2label.items()}
                else:
                    label2id = cfg.get("label2id") or {}
                    id2label = {int(v): k for k, v in label2id.items()}
                self.id2label = id2label  # type: ignore[assignment]
                self.hf = hfdir
        except Exception:
            self.hf = None

    def _regex(self, text: str) -> list[dict[str, Any]]:
        spans: list[dict[str, Any]] = []
        m = re.search(r"\b(20\d{2}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/20\d{2})\b", text)
        if m:
            spans.append({"label": "date_time", "start": m.start(), "end": m.end()})
        m = re.search(r"\b(\$?\d+(?:\.\d{2})?)\b", text)
        if m:
            spans.append({"label": "amount", "start": m.start(), "end": m.end()})
        for kw, lbl in [("prod", "env"), ("uat", "env"), ("sla", "sla")]:
            i = text.lower().find(kw)
            if i >= 0:
                spans.append({"label": lbl, "start": i, "end": i + len(kw)})
        return spans

    def infer(self, text: str):
        if not self.hf:
            return self._regex(text)
        return self._regex(text)

    def extract(self, text: str):
        return self.infer(text)
