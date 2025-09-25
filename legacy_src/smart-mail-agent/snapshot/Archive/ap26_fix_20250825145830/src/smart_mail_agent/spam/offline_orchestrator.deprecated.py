# deprecated; use spam_filter_orchestrator.py
from __future__ import annotations

from . import orchestrator_offline as _impl

Thresholds = _impl.Thresholds
SpamFilterOrchestratorOffline = _impl.SpamFilterOrchestratorOffline
orchestrate = _impl.orchestrate
_main = _impl._main
__all__ = ["Thresholds", "SpamFilterOrchestratorOffline", "orchestrate", "_main"]
