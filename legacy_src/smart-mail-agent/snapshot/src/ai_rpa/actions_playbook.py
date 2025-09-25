# pragma: no cover
from __future__ import annotations
from typing import Iterable, List, Dict, Any
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # pragma: no cover

def load_playbook(path: str | Path) -> Dict[str, Any] | None:
    if yaml is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return None

def plan_with_playbook(intents: Iterable[str], pb: Dict[str, Any] | None) -> List[str]:
    if not pb:
        return []
    seen, out = set(), []
    ints = [str(x).strip().lower() for x in (intents or []) if str(x).strip()]
    rules = (pb.get("rules") or [])
    for r in rules:
        any_p  = [str(x).lower() for x in (r.get("any")  or [])]
        all_p  = [str(x).lower() for x in (r.get("all")  or [])]
        none_p = [str(x).lower() for x in (r.get("none") or [])]
        def _hit_any():  return (not any_p) or any(k in ints for k in any_p)
        def _hit_all():  return all(k in ints for k in all_p)
        def _hit_none(): return all(k not in ints for k in none_p)
        if _hit_any() and _hit_all() and _hit_none():
            for a in (r.get("actions") or []):
                a = str(a).strip()
                if a and a not in seen:
                    seen.add(a); out.append(a)
    return out
