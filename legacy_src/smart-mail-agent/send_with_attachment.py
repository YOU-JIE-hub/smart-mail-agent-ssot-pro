# Auto-alias shim by AP-15 — do not edit.
# 使 `import send_with_attachment` 直接等同
# `smart_mail_agent.ingestion.integrations.send_with_attachment`
import importlib as _il
import sys as _sys

_mod = _il.import_module("smart_mail_agent.ingestion.integrations.send_with_attachment")
_sys.modules[__name__] = _mod
