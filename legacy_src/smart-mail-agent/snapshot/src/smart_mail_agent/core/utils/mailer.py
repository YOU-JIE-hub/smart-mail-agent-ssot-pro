from __future__ import annotations

from importlib import import_module as _im

_mod = _im("smart_mail_agent.utils.mailer")
__all__ = getattr(_mod, "__all__", [])
for _k in __all__:
    globals()[_k] = getattr(_mod, _k)
del _im, _mod
