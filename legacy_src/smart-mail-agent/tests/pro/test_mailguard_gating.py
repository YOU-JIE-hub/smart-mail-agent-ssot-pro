import json, io, sys, os
from pathlib import Path

def _run(argv):
    from ai_rpa.main import main
    import sys as _s
    old = list(_s.argv)
    try:
        _s.argv = argv
        return main()
    finally:
        _s.argv = old

def _stdout_json(capsys):
    out = capsys.readouterr().out.strip()
    return json.loads(out)

def test_block_skips_actions(tmp_path, monkeypatch, capsys):
    f = tmp_path/"x.txt"; f.write_text("free money!!!", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f)])
    assert rc == 0
    j = _stdout_json(capsys)
    assert j["results"]["spamcheck"]["verdict"] == "BLOCK"
    assert "actions" not in j["results"]
    assert "actions:skipped_by_mailguard" in j["steps"]

def test_allow_runs_actions(tmp_path, capsys):
    f = tmp_path/"y.txt"; f.write_text("想合作 需要方案與報價", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f)])
    assert rc == 0
    j = _stdout_json(capsys)
    assert j["results"]["spamcheck"]["verdict"] == "ALLOW"
    assert isinstance(j["results"]["actions"], list) and len(j["results"]["actions"])>0
