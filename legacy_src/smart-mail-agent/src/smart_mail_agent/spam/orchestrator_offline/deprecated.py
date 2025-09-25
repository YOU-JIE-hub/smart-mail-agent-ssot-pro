"""Deprecated shim module.

This exists only to satisfy tooling that attempts to import
`smart_mail_agent.spam.<name>.deprecated` due to a legacy filename
with an extra dot. No runtime behavior here.
"""

# Optionally forward to canonical if someone imports attributes:
try:
    from smart_mail_agent.spam.spam_filter_orchestrator import *  # noqa: F401,F403
except Exception:
    pass
