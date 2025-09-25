from __future__ import annotations

import argparse
import json
from typing import Any

from smart_mail_agent.transport.smtp_send import send_smtp
from smart_mail_agent.utils.config import paths

META = paths().status / "retry_meta.json"


def _load() -> dict[str, Any]:
    return json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}


def _save(d: dict[str, Any]) -> None:
    META.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> dict[str, Any]:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--max_attempts", type=int, default=3)
    args = ap.parse_args()

    P = paths()
    q = P.outbox / "retry"
    q.mkdir(parents=True, exist_ok=True)

    sent = P.outbox / "sent"
    sent.mkdir(exist_ok=True)

    dead = P.outbox / "dead"
    dead.mkdir(exist_ok=True)

    meta = _load()
    files = sorted(q.glob("*.eml"))[: args.batch]
    retried = 0

    for f in files:
        cnt = int(meta.get(f.name, 0))
        res = send_smtp(f.read_bytes())
        if res.get("sent"):
            (sent / f.name).write_bytes(f.read_bytes())
            f.unlink(missing_ok=True)
            meta.pop(f.name, None)
        else:
            cnt += 1
            if cnt >= args.max_attempts:
                (dead / f.name).write_bytes(f.read_bytes())
                f.unlink(missing_ok=True)
                meta.pop(f.name, None)
            else:
                meta[f.name] = cnt
            retried += 1

    _save(meta)
    out = {"ok": True, "retried": retried, "queue": len(list(q.glob("*.eml")))}
    print(json.dumps(out, ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
