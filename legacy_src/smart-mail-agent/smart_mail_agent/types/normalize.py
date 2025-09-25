from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation

__all__ = ["normalize_env","normalize_amount","normalize_sla","normalize_email"]

def normalize_env(s: str | None) -> str | None:
    if s is None: return None
    m = str(s).strip().lower()
    table = {
        "prod":"prod","production":"prod","prd":"prod",
        "staging":"staging","stage":"staging","preprod":"staging",
        "dev":"dev","development":"dev","devel":"dev",
        "test":"test","testing":"test","qa":"test",
    }
    return table.get(m, m)

def normalize_amount(x) -> float | Decimal | None:
    if x is None: return None
    s = str(x)
    m = re.findall(r'[-+]?\d+(?:[.,]\d+)?', s)
    if not m: return None
    val = m[0].replace(",", "")
    try:
        return float(val)
    except ValueError:
        try:
            return Decimal(val)
        except (InvalidOperation, ValueError):
            return None

def normalize_sla(s: str | None) -> str | None:
    if s is None: return None
    t = str(s).strip().lower()
    table = {"p0":"P0","p1":"P1","p2":"P2","p3":"P3","sev1":"P1","sev2":"P2","sev3":"P3"}
    return table.get(t, t.upper())

def normalize_email(s: str | None) -> str | None:
    if s is None: return None
    return str(s).strip().lower()
