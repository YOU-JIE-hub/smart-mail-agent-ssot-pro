from __future__ import annotations

from importlib import import_module
from typing import Any


def _get_core():
    # 延遲載入，避免在 import 階段形成循環
    try:
        return import_module("smart_mail_agent.core.policy_engine")
    except Exception as e:
        raise ImportError("Cannot import smart_mail_agent.core.policy_engine") from e


def apply_policies(*args: Any, **kwargs: Any) -> Any:
    core = _get_core()
    fn = getattr(core, "apply_policies", None)
    if callable(fn):
        return fn(*args, **kwargs)
    # 後備：若核心只提供 apply_policy
    fn2 = getattr(core, "apply_policy", None)
    if callable(fn2):
        return fn2(*args, **kwargs)
    raise ImportError("core.policy_engine has no apply_policies/apply_policy")


def apply_policy(*args: Any, **kwargs: Any) -> Any:
    core = _get_core()
    fn = getattr(core, "apply_policy", None) or getattr(core, "apply_policies", None)
    if callable(fn):
        return fn(*args, **kwargs)
    raise ImportError("core.policy_engine has no apply_policy/apply_policies")


__all__ = ["apply_policies", "apply_policy"]
