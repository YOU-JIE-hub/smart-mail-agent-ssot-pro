from __future__ import annotations

import argparse
import json

from smart_mail_agent.spam.spam_filter_orchestrator import SpamFilterOrchestrator


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sma-spamcheck", description="Spam quick check")
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--from", dest="sender", required=True)
    ns = p.parse_args(argv)
    info = SpamFilterOrchestrator().is_legit(ns.subject, ns.body, ns.sender, [])
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
