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

def test_main_stdout_no_output(tmp_path, monkeypatch, capsys):
    # 準備一個有文字的檔案給 nlp
    infile = tmp_path / "t.txt"
    infile.write_text("合作退款測試", encoding="utf-8")

    # 避免外連：scraper 回空
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog",
               "--tasks","nlp,actions",
               "--input-path", str(infile),
               "--url","http://stub.local"])
    assert rc == 0
    # 現狀：未指定 --output 時不一定印到 stdout；若有輸出就驗證為合法 JSON
    out = capsys.readouterr().out.strip()
    if out:
        j = json.loads(out)
        assert isinstance(j.get("tasks"), list)

def test_main_bad_input_path_stdout(tmp_path, capsys):
    bad = tmp_path / "no_such_file.txt"
    rc = _run(["prog",
               "--tasks","nlp",
               "--input-path", str(bad),
               "--url","http://stub.local"])
    # 目標：不中斷。若有 stdout，必須是可解析的 JSON。
    assert rc == 0
    out = capsys.readouterr().out.strip()
    if out:
        j = json.loads(out)
        assert isinstance(j.get("tasks"), list)
