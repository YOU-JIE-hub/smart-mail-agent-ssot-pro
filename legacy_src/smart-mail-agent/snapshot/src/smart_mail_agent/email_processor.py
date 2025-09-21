# DEPRECATED SHIM — re-export to 'smart_mail_agent.ingestion.email_processor'
# Created by AP-05. Keep runtime compatible while enforcing canonical imports.
from smart_mail_agent.ingestion.email_processor import *  # noqa: F401,F403

__all__ = [n for n in globals().keys() if not n.startswith("_")]
