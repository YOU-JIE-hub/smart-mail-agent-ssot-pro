from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ActionContext:
    db_path: Path
    out_root: Path
    offline: bool = False
    env: dict[str, Any] = field(default_factory=dict)

    def outbox_dir(self) -> Path:
        p = self.out_root / "rpa_out" / "email_outbox"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def tickets_dir(self) -> Path:
        p = self.out_root / "rpa_out" / "tickets"
        p.mkdir(parents=True, exist_ok=True)
        return p
