from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .audit_db import DEFAULT_DB, AuditDB


class Audit:
    def __init__(self, project_root: Path) -> None:
        self.root = Path(project_root)
        self.db_path = self.root / DEFAULT_DB
        self.nd_path = self.root / "reports_auto" / "logs" / "pipeline.ndjson"
        self.nd_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = AuditDB(self.db_path)

    def _now(self) -> int:
        return int(time.time())

    def log(self, stage: str, level: str, meta: dict[str, Any]) -> None:
        # 統一事件欄位
        rec = {
            "ts": self._now(),
            "level": level,
            "event": meta.get("event") or f"{stage}",
            "stage": stage,
            "mail_id": meta.get("mail_id"),
            "intent": meta.get("intent"),
            "action": meta.get("action"),
            "idempotency_key": meta.get("idempotency_key"),
            "duration_ms": meta.get("duration_ms"),
            "trace_id": meta.get("trace_id") or str(uuid.uuid4()),
            "span_id": meta.get("span_id") or str(uuid.uuid4()),
            "error": meta.get("error"),
            "attributes": meta.get("attributes") or {},
        }
        # 1) 寫入 NDJSON
        with self.nd_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        # 2) 同步必要 DB 記錄（可冪等）
        if stage == "ingest" and rec.get("mail_id"):
            self.db.insert(
                "mails",
                {
                    "mail_id": rec["mail_id"],
                    "subject": meta.get("subject", ""),
                    "ts": rec["ts"],
                },
            )

        if rec.get("action") and rec.get("mail_id"):
            self.db.insert(
                "actions",
                {
                    "ts": rec["ts"],
                    "mail_id": rec["mail_id"],
                    "intent": rec.get("intent") or "other",
                    "action": rec["action"],
                    "idempotency_key": rec.get("idempotency_key") or str(uuid.uuid4()),
                    "priority": meta.get("priority") or "P3/Ops",
                    "queue": meta.get("queue") or meta.get("priority") or "P3/Ops",
                    "status": meta.get("status") or "queued",
                },
            )

    # 便捷 DB API（給 action_handler 用）
    def insert_row(self, table: str, rec: dict[str, Any]) -> None:
        self.db.insert(table, rec)
