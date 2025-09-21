__all__ = ["ocr", "mail_io", "actions_executor", "file_classifier", "spam_adapter", "actions","intent_map","mailguard","utils","nlp","nlp_llm","scraper","main"]
from . import ocr,  mail_io,  actions_executor,  file_classifier,  spam_adapter,  actions, intent_map, mailguard, nlp, nlp_llm, scraper, main
# PEP 562 fallback：即使個別檔缺失也不會在 import 期炸掉（回傳空模組樣式）
def __getattr__(name):
    import types
    if name in __all__:
        m = types.ModuleType(f"ai_rpa.{name}")
        return m
    raise AttributeError(name)
from . import mailguard
from . import nlp
from . import nlp_llm
from . import scraper
from . import spam_adapter
from . import file_classifier
from . import actions_executor
from . import mail_io
