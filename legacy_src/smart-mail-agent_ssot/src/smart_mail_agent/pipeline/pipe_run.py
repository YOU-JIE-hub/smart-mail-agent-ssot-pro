from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from typing import Any

from smart_mail_agent.actions.router import route
from smart_mail_agent.ingest.eml_dir import load_dir
from smart_mail_agent.ingest.imap_pull import pull_imap
from smart_mail_agent.ml import infer
from smart_mail_agent.policy.engine import apply_policies
from smart_mail_agent.utils.config import paths
from smart_mail_agent.utils.crash import crash_dump
from smart_mail_agent.utils.logger import time_ms


def _ts() -> str:
    return time.strftime("%Y%m%dT%H%M%S")


def gate(xs: list[dict[str, Any]]) -> dict[str, int]:
    d: dict[str, int] = {"done": 0, "error": 0, "queued": 0}
    for a in xs:
        st = a.get("status", "queued")
        d[st] = d.get(st, 0) + 1
    for k in ("done", "error", "queued"):
        d.setdefault(k, 0)
    return d


def _ensure_samples(p) -> None:
    samples = p.root / "samples" / "inbox"
    samples.mkdir(parents=True, exist_ok=True)
    if any(samples.glob("*.txt")):
        return
    ss = [
        "您好，想詢問上一張報價是否還有效？",
        "我要查詢貨件的追蹤號碼，謝謝。",
        "請問可否開立發票抬頭為 AAA？",
        "前次詢價，是否可提供折扣與交期？",
    ]
    for i, t in enumerate(ss, 1):
        (samples / f"mail_{i:02d}.txt").write_text(t, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", choices=["samples", "dir", "imap"], default="samples")
    ap.add_argument("--dir", default=None)
    args = ap.parse_args()

    p = paths()
    _ensure_samples(p)

    if args.inbox == "samples":
        mails = load_dir(str(p.root / "samples" / "inbox"))
    elif args.inbox == "dir":
        mails = load_dir(args.dir or str(p.root / "samples" / "inbox"))
    else:
        cfg = {
            "host": os.getenv("IMAP_HOST"),
            "port": os.getenv("IMAP_PORT"),
            "user": os.getenv("IMAP_USER"),
            "pass": os.getenv("IMAP_PASS"),
            "ssl": os.getenv("IMAP_SSL", "1") == "1",
            "mailbox": os.getenv("IMAP_MAILBOX", "INBOX"),
        }
        mails = pull_imap(cfg)

    actions: list[dict[str, Any]] = []
    for m in mails[:10]:
        t0 = time_ms()
        try:
            sp = infer.predict_spam(m["body"])
            if sp.get("label") == "spam":
                actions.append(
                    {
                        "id": m["id"],
                        "status": "done",
                        "spam": sp,
                        "intent": {"intent": "spam", "score": sp["score"], "needs_review": False, "top2": []},
                        "kie": {"ok": True, "fields": {}, "coverage": {}},
                        "artifacts": [],
                        "outbox": [],
                        "alerts": [{"level": "low", "message": "spam filtered"}],
                        "tickets": [],
                        "latency_ms": time_ms() - t0,
                        "ts": _ts(),
                    }
                )
                continue

            it = infer.predict_intent(m["body"])
            kie = (
                infer.extract_kie(m["body"])
                if it.get("intent") in {"quote", "order", "invoice", "logistics", "warranty", "general"}
                else {"ok": True, "fields": {}, "coverage": {}}
            )
            pol = apply_policies(
                {"mail": m, "intent": it.get("intent"), "kie": kie, "intent_score": it.get("score", 0.0)}
            )
            act = route(m, it.get("intent"), kie)
            actions.append(
                {
                    "id": m["id"],
                    "status": "done",
                    "spam": sp,
                    "intent": it,
                    "kie": kie,
                    "alerts": pol.get("alerts", []),
                    "tickets": pol.get("tickets", []),
                    "artifacts": act.get("artifacts", []),
                    "outbox": act.get("outbox", []),
                    "needs_review": it.get("needs_review") or act.get("needs_review"),
                    "latency_ms": time_ms() - t0,
                    "ts": _ts(),
                }
            )
        except Exception as e:
            crash_dump("PIPE_HANDLE", f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=2)}")
            actions.append(
                {
                    "id": m.get("id", "?"),
                    "status": "error",
                    "error": str(e),
                    "ts": _ts(),
                    "latency_ms": time_ms() - t0,
                }
            )

    out = p.status / f"ACTIONS_{_ts()}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for a in actions:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    dist = gate(actions)
    summ = {
        "ts": _ts(),
        "inbox_count": len(mails),
        "evaluated": len(actions),
        "distribution": dist,
        "pass_rule": "done=10,error=0,queued=0",
        "actions_jsonl": str(out),
    }
    (p.status / f"PIPE_SUMMARY_{_ts()}.json").write_text(
        json.dumps(summ, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"ok": (dist.get("error", 0) == 0), **summ}, ensure_ascii=False))


if __name__ == "__main__":
    main()
