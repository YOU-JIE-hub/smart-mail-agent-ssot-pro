from __future__ import annotations

import re


def _mask(s: str, keep: int = 3) -> str:
    if not s:
        return s
    if len(s) <= keep * 2:
        return "…" * len(s)
    return s[:keep] + "…" + s[-keep:]


def email(v: str) -> str:
    if not v:
        return v
    m = re.match(r"([^@]+)@(.+)", v)
    return f"{_mask(m.group(1))}@{m.group(2)}" if m else v


def phone(v: str) -> str:
    return _mask(v or "", keep=3)


def iban(v: str) -> str:
    return _mask(v or "", keep=4)


def redact_text(t: str) -> str:
    if not t:
        return t
    t = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        lambda m: email(m.group(0)),
        t,
    )
    t = re.sub(
        r"\b\d{3}[-\s]?\d{3,4}[-\s]?\d{3,4}\b",
        lambda m: phone(m.group(0)),
        t,
    )
    return t
