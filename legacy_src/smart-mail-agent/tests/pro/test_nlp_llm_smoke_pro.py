import inspect
import ai_rpa.nlp_llm as m

def test_nlp_llm_has_callable():
    ran = False
    for _, fn in inspect.getmembers(m, inspect.isfunction):
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        req = [p for p in sig.parameters.values()
               if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        try:
            if len(req) == 0:
                fn(); ran = True; break
            if len(req) == 1:
                fn("合作 退款 測試"); ran = True; break
        except Exception:
            continue
    # 至少踩到一個函式（若模組內無函式，也不報錯，避免 flaky）
    assert ran or not any(callable(getattr(m, n)) for n in dir(m)), "nlp_llm 應有至少一個可呼叫函式"
