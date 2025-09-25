from __future__ import annotations
import importlib, os, sys, inspect

def _smoke_callables(mod):
    for n in dir(mod):
        obj = getattr(mod, n)
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                kwargs = {}
                if "text" in sig.parameters: kwargs["text"] = "測試"
                if "model" in sig.parameters: kwargs["model"] = "stub-model"
                try:
                    obj(**kwargs)
                except Exception:
                    pass
            except Exception:
                pass

def test_import_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    if "ai_rpa.nlp_llm" in sys.modules:
        del sys.modules["ai_rpa.nlp_llm"]
    M = importlib.import_module("ai_rpa.nlp_llm")
    _smoke_callables(M)

def test_import_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    if "ai_rpa.nlp_llm" in sys.modules:
        del sys.modules["ai_rpa.nlp_llm"]
    M = importlib.import_module("ai_rpa.nlp_llm")
    _smoke_callables(M)
