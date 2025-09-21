from pathlib import Path
from .conftest import run_script

def test_spam_quick_eval_runs(tmp_path, tiny_spam_jsonl, tiny_thresholds, monkeypatch):
    out = tmp_path/"report.md"
    # 修復 _spam_common 匯入別名（若腳本需要）
    (Path("_spam_common.py")).write_text("from scripts._sma_common import spam_signals as signals, text_of\n", encoding="utf-8")
    run_script(Path("scripts/sma_quick_eval.py"), [
        "--data", str(tiny_spam_jsonl),
        "--model", "artifacts_prod/model_pipeline.pkl",       # joblib 不會被叫用；此腳本內部用 vect/cal 亦可 pathless
        "--thresholds", str(tiny_thresholds),
        "--out", str(out),
    ])
    assert out.exists()
    t = out.read_text(encoding="utf-8")
    assert "[TEXT]" in t and "[RULE]" in t and "[ENS]" in t
