import json, sys, os
from pathlib import Path
from ai_rpa.main import main

def _run(argv):
    old = list(sys.argv)
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def _read(capsys):
    out = capsys.readouterr().out.strip()
    return json.loads(out)

def test_block_skips_actions(tmp_path, monkeypatch, capsys):
    f = tmp_path/"x.txt"; f.write_text("FREE MONEY!!!", encoding="utf-8")
    # 強制 OFFLINE，以避免 scraper 意外連網
    monkeypatch.setenv("OFFLINE","1")
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f)])
    assert rc == 0
    j = _read(capsys)
    assert j["results"]["spamcheck"]["verdict"] == "BLOCK"
    assert "actions" not in j["results"]
    assert "actions:skipped_by_mailguard" in j["steps"]
