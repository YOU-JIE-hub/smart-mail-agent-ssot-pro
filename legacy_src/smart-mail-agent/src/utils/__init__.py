# AP-10 utils shim (strong): bind this package to smart_mail_agent.utils
# and pre-alias common submodules so `import utils.<name>` keeps working.
import importlib as _importlib
import sys as _sys

# 將當前模組對應到 canonical 模組物件（不是單純 re-export）
_canon = _importlib.import_module("smart_mail_agent.utils")
_sys.modules[__name__] = _canon  # 讓 `import utils` 等同於 `smart_mail_agent.utils`

# 常見子模組列表（需要可自行擴充）
_forwards = ("log_writer", "logger", "mailer", "jsonlog", "tracing", "spam_filter")
for _n in _forwards:
    try:
        _sys.modules[f"{__name__}.{_n}"] = _importlib.import_module(f"smart_mail_agent.utils.{_n}")
    except Exception:
        # 子模組不存在就略過，不影響其餘匯入
        pass
