from __future__ import annotations
import re
from typing import List, Tuple

_amount_re = re.compile(r"(?<!\d)(?:usd|nt\$|ntd|twd|\$)?\s*([0-9]{1,3}(?:,[0-9]{3})*|\d+)(?:\.\d{1,2})?", re.I)
_date_re = re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})")
_env_re = re.compile(r"\b(prod|production|staging|stage|test|uat|dev|開發|測試|正式)\b", re.I)
_sla_re = re.compile(r"\bSLA\s*[:：]?\s*(P[0-9]|[0-9]h|[0-9]{1,2}小時|critical|high|medium|low)\b", re.I)

class KIEEngine:
    def extract(self, text: str) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        m = _amount_re.search(text)
        if m: out.append(("amount", m.group(0).strip()))
        m = _date_re.search(text)
        if m: out.append(("date_time", m.group(1).strip()))
        m = _env_re.search(text)
        if m: out.append(("env", m.group(0).strip()))
        m = _sla_re.search(text)
        if m: out.append(("sla", m.group(0).strip()))
        return out
