from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    from ai_rpa.main import main
    old = sys.argv
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_main_unknown_task(tmp_path):
    outp = tmp_path / "out.json"
    rc = _run([
        "prog",
        "--tasks", "unknown_task",
        "--input-path", str(tmp_path),
        "--url", "http://stub.local",
        "--output", str(outp),
    ])
    assert rc == 0
    j = json.loads(outp.read_text(encoding="utf-8"))
    # 應至少回傳成功旗標與 tasks 清單
    assert j.get("ok") is True
    assert isinstance(j.get("tasks"), list)

def test_main_actions_only_no_inputs(tmp_path, monkeypatch):
    # 避免外部連線：scraper 統一回空
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    outp = tmp_path / "out.json"
    rc = _run([
        "prog",
        "--tasks", "actions",
        "--input-path", str(tmp_path),
        "--url", "http://stub.local",
        "--output", str(outp),
    ])
    assert rc == 0
    j = json.loads(outp.read_text(encoding="utf-8"))
    # 應有 results/actions 的骨架（即使為空）
    assert "results" in j
    assert "actions" in j["results"]
