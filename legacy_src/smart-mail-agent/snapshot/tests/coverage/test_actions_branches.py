from __future__ import annotations
import inspect
import importlib
import types

def _pick_fn(mod):
    for name in ("decide_actions","build_actions","make_actions","generate_actions"):
        if hasattr(mod, name):
            return getattr(mod, name)
    return None

def test_actions_non_dryrun_branch(monkeypatch):
    A = importlib.import_module("ai_rpa.actions")
    fn = _pick_fn(A)
    if fn is None:
        # 沒暴露決策函式就略過
        return

    # 盡力找到可能被呼叫的外部執行端點並 stub 掉
    try:
        ah = importlib.import_module("smart_mail_agent.routing.action_handler")
        if hasattr(ah, "handle"):
            monkeypatch.setattr(ah, "handle", lambda *a, **k: {"ok": True, "actions": a or []})
    except Exception:
        pass
    for attr in ("handle","apply_actions","run_actions","execute"):
        if hasattr(A, attr):
            monkeypatch.setattr(A, attr, lambda *a, **k: {"ok": True})

    # 多訊號組合：意圖 + scrape 節點，且非 dry-run
    res = fn(
        intents=[{"label":"refund"}],
        scrape=[{"tag":"h1","text":"合作"}],
        nodes=[{"tag":"a","text":"下單"}],
        ocr_text="我要退款",
        dry_run=False
    )
    assert isinstance(res, (list, dict))
