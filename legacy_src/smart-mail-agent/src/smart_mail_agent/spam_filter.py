from __future__ import annotations

# Back-compat shim: keep legacy import path working
try:
    from smart_mail_agent.spam.orchestrator import (  # type: ignore
        SpamFilterOrchestrator,
        score_spam,
    )
except Exception:
    try:
        from smart_mail_agent.spam.filter import (  # type: ignore
            SpamFilterOrchestrator,
            score_spam,
        )
    except Exception:

        class SpamFilterOrchestrator:  # minimal stub
            def __init__(self, *a, **kw): ...
            def predict(self, text: str) -> float:
                return 0.0

        def score_spam(text: str) -> float:
            return 0.0
