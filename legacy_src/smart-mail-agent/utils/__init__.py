# AP-11 utils shim (root-level): bind this package to smart_mail_agent.utils
# and pre-alias common submodules so `import utils.<name>` keeps working.
import importlib as _il
import sys as _sys

_canon = _il.import_module("smart_mail_agent.utils")
# 先預註冊常見子模組到 sys.modules，再把當前 package 綁定到 canonical
_forwards = ("log_writer", "logger", "mailer", "jsonlog", "tracing", "spam_filter")
for _n in _forwards:
    try:
        _sys.modules[f"{__name__}.{_n}"] = _il.import_module(f"smart_mail_agent.utils.{_n}")
    except Exception:
        pass

_sys.modules[__name__] = _canon  # 讓 `import utils` 等同 `smart_mail_agent.utils`
