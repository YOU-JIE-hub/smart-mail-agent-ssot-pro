import os
import pathlib
import pytest

skip = pytest.mark.skipif(os.getenv("SMA_E2E_SMOKE") != "1", reason="SMA_E2E_SMOKE!=1")

def _find_base():
    for c in (pathlib.Path("reports_auto/e2e_mail"), pathlib.Path("reports_auto/e2e_run")):
        if c.exists():
            return c
    return None

@skip
def test_e2e_outputs_exist():
    base = _find_base()
    assert base is not None, "找不到 e2e_mail 或 e2e_run 產出根目錄"
    runs = list(base.glob("*"))
    assert runs, f"{base} 下沒有任何 run"
    latest = max(runs, key=lambda p: p.stat().st_mtime)
    assert (latest / "cases.jsonl").exists(), "缺少 cases.jsonl"
    assert (latest / "actions.jsonl").exists(), "缺少 actions.jsonl"
    assert (latest / "SUMMARY.md").exists(), "缺少 SUMMARY.md"
