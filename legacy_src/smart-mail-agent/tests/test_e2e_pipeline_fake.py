import json, types, sys
from pathlib import Path
from .conftest import run_script, _FakeSpamModel, _FakeIntentModel

def test_e2e_sma_e2e_run(tmp_path, monkeypatch):
    # 準備 cases
    cases = tmp_path/"cases.jsonl"
    rows = [
        {"id":"q1","subject":"","body":"Need quote NT$5000 by 2025-09-30"},
        {"id":"t1","subject":"","body":"cannot login; error 500 please help"},
        {"id":"s1","subject":"","body":"verify your account http://bad.xyz"},
    ]
    cases.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows), encoding="utf-8")
    out_dir = tmp_path/"e2e"

    # 匯入模組後，覆寫其 load 函式，使其回傳 Fake
    m = sys.modules.get("scripts.sma_e2e_run")
    if m:
        del sys.modules["scripts.sma_e2e_run"]
    mod = __import__("scripts.sma_e2e_run", fromlist=['*'])

    def fake_spam_load(*a, **k): return _FakeSpamModel(), {"threshold":0.4,"signals_min":2}
    def fake_intent_load(*a, **k): return _FakeIntentModel(), {"p1":0.5,"margin":0.1,"policy_lock":True}
    def fake_kie_load(*a, **k): return object(), object(), ["O","B-amount","I-amount","B-date_time","I-date_time","B-env","I-env","B-sla","I-sla"]

    mod.spam_load = fake_spam_load
    mod.intent_load = fake_intent_load
    mod.kie_load = fake_kie_load

    run_script(Path("scripts/sma_e2e_run.py"), [
        "--cases", str(cases),
        "--kie_dir", "reports_auto/kie/kie",
        "--out_dir", str(out_dir)
    ])

    summ = out_dir/"SUMMARY.md"
    assert summ.exists()
    t = summ.read_text(encoding="utf-8")
    assert "Spam" in t and "Intent" in t
