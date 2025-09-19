from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from smart_mail_agent.observability.audit import Audit
from smart_mail_agent.rpa.policy import answer_policy_question
from smart_mail_agent.transport.mail import send_file_transport, send_smtp
from smart_mail_agent.utils.pdf_safe import write_pdf_or_txt

ACTIONS = {
    "biz_quote": "create_quote_ticket",
    "tech_support": "create_support_ticket",
    "complaint": "send_apology",
    "policy_qa": "answer_policy_question",
    "profile_update": "generate_profile_diff",
    "manual_triage": "manual_triage",
    "quarantine": "do_quarantine",
    "other": "manual_triage",
}
PRIORITY = {
    "do_quarantine": "P1/Sec",
    "create_support_ticket": "P1/Support",
    "send_apology": "P2/CS",
    "answer_policy_question": "P2/CS",
    "generate_profile_diff": "P2/Ops",
    "manual_triage": "P3/Ops",
}


def _ide_key(meta: dict) -> str:
    blob = json.dumps(meta, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def plan_actions(cases, outdir: Path, project_root: Path | None = None) -> None:
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
    audit = Audit(project_root or Path(__file__).resolve().parents[3])

    for c in cases:
        a = ACTIONS.get(c.get("intent", "other"), "manual_triage")
        meta = {"mail_id": c.get("id"), "intent": c.get("intent"), "action": a, "ts": int(time.time())}
        meta["idempotency_key"] = _ide_key(meta)
        meta["priority"] = PRIORITY.get(a, "P3/Ops")
        meta["queue"] = meta["priority"]
        # 寫 plan（向後相容）
        plan.open("a", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False) + "\n")

        # 依 Action 分支執行最小副作用 + DB/LOG
        if a == "do_quarantine":
            audit.insert_row(
                "alerts",
                {
                    "ts": meta["ts"],
                    "mail_id": meta["mail_id"],
                    "severity": "high",
                    "channel": "quarantine",
                    "message": "spam suspected",
                },
            )
            audit.log("plan", "INFO", {**meta, "event": "spam.quarantine", "status": "queued"})
            continue

        if a == "create_support_ticket":
            tfile = tickets / f"{meta['mail_id']}.json"
            tfile.write_text(
                json.dumps({"id": meta["mail_id"], "status": "open"}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            audit.insert_row(
                "tickets",
                {
                    "ts": meta["ts"],
                    "mail_id": meta["mail_id"],
                    "type": "tech_support",
                    "status": "open",
                    "payload": json.dumps({"subject": c.get("subject", "")}, ensure_ascii=False),
                },
            )
            audit.log("rpa", "INFO", {**meta, "event": "intent.tech_support.created", "status": "created"})
            continue

        if a == "generate_profile_diff":
            diff = {"name": "TBD", "phone": "TBD"}  # 真實場景：由 KIE/規則生成
            df = outdir / f"{meta['mail_id']}_profile_diff.json"
            df.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
            audit.insert_row(
                "changes",
                {
                    "ts": meta["ts"],
                    "mail_id": meta["mail_id"],
                    "diff_json": json.dumps(diff, ensure_ascii=False),
                    "status": "pending_review",
                },
            )
            audit.log("rpa", "INFO", {**meta, "event": "intent.profile_update.diff", "status": "pending_review"})
            continue

        if a == "answer_policy_question":
            text = answer_policy_question((c.get("subject") or "") + "\n" + (c.get("body") or ""))
            audit.insert_row(
                "answers",
                {
                    "ts": meta["ts"],
                    "mail_id": meta["mail_id"],
                    "source": "rag",
                    "kb_hits": 1,
                    "latency_ms": 5,
                    "content": text,
                },
            )
            # 出站：優先 SMTP，失敗則 file-transport
            payload = {"mail_id": meta["mail_id"], "subject": c.get("subject", ""), "body": c.get("body", "")}
            rec = {"subject": "Re: " + (c.get("subject") or ""), "text": text, "payload": payload}
            try:
                send_smtp(rec)
                audit.log("transport", "INFO", {**meta, "event": "policy.answer.sent", "status": "sent"})
            except Exception as e:
                outp = send_file_transport(outdir.parent, rec)
                audit.log(
                    "transport",
                    "WARN",
                    {
                        **meta,
                        "event": "policy.answer.degraded",
                        "status": "file-transport",
                        "attributes": {"path": str(outp)},
                        "error": str(e),
                    },
                )
            continue

        if a == "create_quote_ticket":
            amount = 1234.56  # 示例
            outpdf = outdir / f"{meta['mail_id']}_quote.pdf"
            real = write_pdf_or_txt(str(outpdf), f"Quote for {meta['mail_id']}\nAmount: {amount}")
            audit.insert_row(
                "quotes",
                {
                    "ts": meta["ts"],
                    "mail_id": meta["mail_id"],
                    "file_path": real,
                    "amount": amount,
                    "status": "ok" if real.endswith(".pdf") else "degraded",
                },
            )
            audit.log(
                "rpa",
                "INFO",
                {
                    **meta,
                    "event": "biz_quote.generated",
                    "status": "ok" if real.endswith(".pdf") else "degraded",
                    "attributes": {"path": real},
                },
            )
            continue

        if a == "send_apology":
            payload = {"mail_id": meta["mail_id"]}
            rec = {"subject": "我們很抱歉", "text": "已收到您的意見，將盡速改善。", "payload": payload}
            try:
                send_smtp(rec)
                audit.log("transport", "INFO", {**meta, "event": "complaint.apology.sent", "status": "sent"})
            except Exception as e:
                outp = send_file_transport(outdir.parent, rec)
                audit.log(
                    "transport",
                    "WARN",
                    {
                        **meta,
                        "event": "complaint.apology.degraded",
                        "status": "file-transport",
                        "attributes": {"path": str(outp)},
                        "error": str(e),
                    },
                )
            continue

        # default: manual_triage
        audit.insert_row("triage", {"ts": meta["ts"], "mail_id": meta["mail_id"], "reason": "fallback"})
        audit.log("rpa", "INFO", {**meta, "event": "manual.triage", "status": "queued"})
