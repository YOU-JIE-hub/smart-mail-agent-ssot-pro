# Auto-generated compat proxy: src/spam/feature_extractor.py
from importlib import import_module as _imp

_mod = _imp("smart_mail_agent.spam.feature_extractor")
# re-export public names
for _k in dir(_mod):
    if not _k.startswith("_"):
        globals()[_k] = getattr(_mod, _k)
