from __future__ import annotations

#!/usr/bin/env python3
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def _template_dirs() -> list[str]:
    here = Path(__file__).resolve()
    roots = [
        here.parents[2],  # repo root
        here.parents[1],  # src/
        Path.cwd(),
    ]
    dirs = []
    for r in roots:
        for p in [r / "templates", r / "src" / "templates", r / "src" / "src" / "templates"]:
            if p.exists():
                dirs.append(str(p))
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            out.append(d)
            seen.add(d)
    return out


_env: Environment | None = None


def get_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(_template_dirs()),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env


def render(template_name: str, context: dict) -> str:
    return get_env().get_template(template_name).render(**context)
