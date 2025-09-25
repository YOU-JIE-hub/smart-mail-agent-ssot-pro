from __future__ import annotations
from pathlib import Path
from time import time

def _whitelist() -> set[str]:
    import os
    wl = os.getenv("SMA_EMAIL_WHITELIST","")
    return {e.strip().lower() for e in wl.split(",") if e.strip()}

def check_recipient(to_addr: str) -> None:
    wl = _whitelist()
    if wl and to_addr.lower() not in wl:
        raise PermissionError(f"recipient {to_addr} not in whitelist")

class _Rate:
    def __init__(self, cap:int): self.cap=cap; self.w=[]; self.T=60.0
    def allow(self)->bool:
        t=time(); self.w=[x for x in self.w if t-x<self.T]
        if self.cap and len(self.w)>=self.cap: return False
        self.w.append(t); return True

_rate = _Rate(int(__import__("os").getenv("SMA_ACTION_CAP_SEND_EMAIL","200")))

def check_rate() -> None:
    if not _rate.allow():
        raise RuntimeError("rate_limited")

def should_skip_resend(eml_path: Path) -> bool:
    import os
    return eml_path.exists() and os.getenv("FORCE_RESEND","0")!="1"
