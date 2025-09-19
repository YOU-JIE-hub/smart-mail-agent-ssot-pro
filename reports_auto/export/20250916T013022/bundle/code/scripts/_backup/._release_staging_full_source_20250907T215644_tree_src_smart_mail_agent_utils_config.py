from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass


def env_bool(k: str, d: bool = False) -> bool:
    v = os.getenv(k)
    return d if v is None else str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def env_str(k: str, d: str = "") -> str:
    v = os.getenv(k)
    return v if v is not None else d


@dataclass(frozen=True)
class Paths:
    root: pathlib.Path
    reports: pathlib.Path
    logs: pathlib.Path
    status: pathlib.Path
    kb_src: pathlib.Path
    kb_index: pathlib.Path
    artifacts_store: pathlib.Path
    crash_bundles: pathlib.Path
    outbox: pathlib.Path


def paths() -> Paths:
    root = pathlib.Path(".").resolve()
    reports = root / "reports_auto"
    p = Paths(
        root=root,
        reports=reports,
        logs=reports / "logs",
        status=reports / "status",
        kb_src=reports / "kb" / "src",
        kb_index=reports / "kb" / "faiss_index",
        artifacts_store=reports / "artifacts_store",
        crash_bundles=reports / "crash_bundles",
        outbox=reports / "outbox",
    )
    for d in (p.logs, p.status, p.kb_src, p.kb_index, p.artifacts_store, p.crash_bundles, p.outbox):
        d.mkdir(parents=True, exist_ok=True)
    return p


OPENAI_KEY = "OPENAI_API_KEY"
SMA_DB_PATH = "SMA_DB_PATH"
SMA_FONT_PATH = "SMA_FONT_PATH"
SMA_KB_INDEX_NAME = "SMA_KB_INDEX_NAME"
SEND_NOW = "SEND_NOW"
