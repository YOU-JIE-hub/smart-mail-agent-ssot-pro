from __future__ import annotations
import inspect
import pytest

def _call_with_best_effort(fn, **candidates):
    """依函式簽名從 candidates 擷取可用 kwargs 呼叫。"""
    sig = inspect.signature(fn)
    kwargs = {k: v for k, v in candidates.items() if k in sig.parameters}
    return fn(**kwargs)

def test_actions_decision_smoke():
    import ai_rpa.actions as A
    # 常見命名：任一個存在即可
    for name in ("decide_actions", "build_actions", "make_actions", "generate_actions"):
        if hasattr(A, name):
            fn = getattr(A, name)
            break
    else:
        pytest.skip("actions 模組未暴露可直接呼叫的決策函式")

    res = _call_with_best_effort(
        fn,
        intents=[{"label": "refund"}],
        scrape=[{"tag": "h1", "text": "退款"}],
        nodes=[{"tag": "a", "text": "合作"}],
        ocr_text="我要退款",
        dry_run=True,
    )
    assert isinstance(res, (list, dict))
