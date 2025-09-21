from __future__ import annotations
from pathlib import Path
__all__ = ["read_eml_paths"]
def read_eml_paths(root: str) -> list[str]:
    p = Path(root)
    return [str(x) for x in sorted(p.glob("*.eml"))]
