from __future__ import annotations

from smart_mail_agent.features.quote_logger import (
    ensure_db_exists,
    get_latest_quote,
    log_quote,
)

__all__ = ["ensure_db_exists", "log_quote", "get_latest_quote"]
