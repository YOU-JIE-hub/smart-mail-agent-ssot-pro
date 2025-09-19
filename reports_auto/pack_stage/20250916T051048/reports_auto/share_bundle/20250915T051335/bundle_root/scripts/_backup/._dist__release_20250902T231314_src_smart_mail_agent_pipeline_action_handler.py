#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/pipeline/action_handler.py
# 模組用途
#   將意圖轉成 RPA 動作腳本與產物。
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ACTIONS = {
    "biz_quote": "create_quote_ticket",
    "tech_support": "create_support_ticket",
    "complaint": "manual_triage",
    "policy_qa": "auto_reply_policy",
    "profile_update": "manual_triage",
    "other": "manual_triage",
}
PRIORITY = {"create_quote_ticket": "P2/Sales", "create_support_ticket": "P1/Support", "manual_triage": "P3/Ops"}


def _ide_key(meta: dict[str, Any]) -> str:
    j = json.dumps(meta, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(j.encode("utf-8")).hexdigest()[:16]


def plan_actions(cases: list[dict[str, Any]], outdir: Path) -> None:
    """參數: cases/outdir；回傳: 無（在 outdir 建立腳本與計畫 ndjson）。"""
    outdir.mkdir(parents=True, exist_ok=True)
    tickets = outdir / "tickets"
    emails = outdir / "email_outbox"
    scripts = outdir
    tickets.mkdir(exist_ok=True)
    emails.mkdir(exist_ok=True)
    (scripts / "do_quarantine.sh").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\necho "[do_quarantine] idempotency_key=${IDEMPOTENCY_KEY}"\n',
        encoding="utf-8",
    )
    (scripts / "do_manual_triage.sh").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\necho "[do_manual_triage] idempotency_key=${IDEMPOTENCY_KEY}"\n',
        encoding="utf-8",
    )
    plan = outdir.parent / "actions_plan.ndjson"
    jl: list[dict[str, Any]] = []
    for c in cases:
        a = ACTIONS.get(c.get("intent", "other"), "manual_triage")
        meta = {"mail_id": c.get("id"), "intent": c.get("intent"), "action": a, "ts": int(time.time())}
        meta["idempotency_key"] = _ide_key(meta)
        meta["priority"] = PRIORITY.get(a, "P3/Ops")
        meta["queue"] = meta["priority"]
        jl.append(meta)
        plan.open("a", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False) + "\n")
