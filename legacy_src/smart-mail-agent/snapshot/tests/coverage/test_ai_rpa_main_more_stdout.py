from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def test_stdout_allow_online(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "t.txt"
    infile.write_text("合作退款測試", encoding="utf-8")
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])
    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local","--allow-online"])
    assert rc == 0
    j = json.loads(capsys.readouterr().out.strip())
    assert j.get("ok") is True and "results" in j and "nlp" in j["results"]

def test_stdout_nlp_only(tmp_path, capsys):
    infile = tmp_path / "only_nlp.txt"
    infile.write_text("單純做 NLP 測試", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = json.loads(capsys.readouterr().out.strip())
    assert j.get("ok") is True
    assert j.get("tasks") == ["nlp"]
    assert "nlp" in j.get("results", {})
