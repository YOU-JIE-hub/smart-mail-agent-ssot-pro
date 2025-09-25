import json
from pathlib import Path
from .conftest import run_script, _FakeIntentModel

def test_intent_router_with_thresholds(tmp_path, monkeypatch):
    # 1) 準備資料
    data = tmp_path/"intent.jsonl"
    rows = [
        {"id":"q1","text":"Please send quote for NT$5000"},
        {"id":"t1","text":"cannot login error 500"},
        {"id":"c1","text":"I am angry, refund now"},
        {"id":"p1","text":"question about policy terms"},
        {"id":"u1","text":"please update phone"},
        {"id":"o1","text":"hi there"},
    ]
    data.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows), encoding="utf-8")
    thr = tmp_path/"thr.json"
    thr.write_text(json.dumps({"p1":0.5,"margin":0.1,"policy_lock":True}), encoding="utf-8")

    # 2) 讓 joblib.load 回傳 FakeIntentModel
    import types, sys
    jl = types.SimpleNamespace()
    jl.load = lambda *_a, **_k: _FakeIntentModel()
    sys.modules["joblib"] = jl

    # 3) 跑 router
    out = tmp_path/"preds.jsonl"
    run_script(Path(".sma_tools/runtime_threshold_router.py"), [
        "--model", "artifacts/intent_pro_cal.pkl",
        "--input", str(data),
        "--config", str(thr),
        "--out_preds", str(out),
        "--eval",
    ])
    assert out.exists()
    s = out.read_text(encoding="utf-8")
    assert "biz_quote" in s and "tech_support" in s and "complaint" in s
