# DEPRECATED SHIM — re-export to 'smart_mail_agent.core.classifier'
# Created by AP-05. Keep runtime compatible while enforcing canonical imports.
from smart_mail_agent.core.classifier import *  # noqa: F401,F403

__all__ = [n for n in globals().keys() if not n.startswith("_")]
