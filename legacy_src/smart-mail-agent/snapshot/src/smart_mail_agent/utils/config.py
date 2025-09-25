from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    offline: bool = bool(int(os.getenv("OFFLINE", "1") in ("1", "true", "True")))
    smtp_host: str = os.getenv("SMTP_HOST", "localhost")
    smtp_port: int = int(os.getenv("SMTP_PORT", "25"))
    imap_host: str = os.getenv("IMAP_HOST", "localhost")
    request_timeout_s: int = int(os.getenv("REQUEST_TIMEOUT_S", "30"))
    demo_language: str = os.getenv("DEMO_LANGUAGE", "zh-TW")


SETTINGS = Settings()
