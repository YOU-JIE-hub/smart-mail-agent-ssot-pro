# Auto-generated compat proxy: src/spam/rules.py
from importlib import import_module as _imp

_mod = _imp("smart_mail_agent.spam.rules")
# re-export public names
for _k in dir(_mod):
    if not _k.startswith("_"):
        globals()[_k] = getattr(_mod, _k)
