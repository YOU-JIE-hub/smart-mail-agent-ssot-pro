from __future__ import annotations
import inspect

def test_nlp_llm_import_and_callable():
    import ai_rpa.nlp_llm as M
    callables = []
    for n in dir(M):
        obj = getattr(M, n)
        if callable(obj):
            # 盡量挑帶 text 參數的函式做輕量呼叫（忽略失敗，重點是可導入）
            try:
                sig = inspect.signature(obj)
                if "text" in sig.parameters:
                    try:
                        obj("測試")
                    except Exception:
                        pass
            except Exception:
                pass
            callables.append(n)
    assert len(callables) >= 1
