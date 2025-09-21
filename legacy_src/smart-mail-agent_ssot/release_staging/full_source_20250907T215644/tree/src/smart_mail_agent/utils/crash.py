from __future__ import annotations

from datetime import datetime

from .config import paths


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S")


def crash_dump(phase: str, detail: str) -> str:
    p = paths()
    ts = _ts()
    cdir = p.crash_bundles / ts
    cdir.mkdir(parents=True, exist_ok=True)
    cfile = cdir / f"CRASH_{phase}_{ts}.log"
    cfile.write_text(f"[CRASH] phase={phase} ts={ts}\n{detail}\n", encoding="utf-8")
    (p.logs / "LAST_CRASH_PATH.txt").write_text(str(cfile), encoding="utf-8")
    return str(cfile)
