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

def _out(capsys):
    out = capsys.readouterr().out.strip()
    assert out
    return json.loads(out)

def test_mailguard_blocks_actions(tmp_path, monkeypatch, capsys):
    f = tmp_path/"x.txt"; f.write_text("free money!!!", encoding="utf-8")
    # 強制 mailguard 回 BLOCK
    import ai_rpa.mailguard.detector as detector
    monkeypatch.setattr(detector, "detect", lambda text, headers=None: {"verdict":"BLOCK","score":0.9,"reasons":["kw"]})
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert j["results"]["spamcheck"]["verdict"] == "BLOCK"
    assert "actions" not in j["results"]
    assert any(s == "actions:skipped_by_mailguard" for s in j["steps"])

def test_mailguard_alias_spamcheck(tmp_path, monkeypatch, capsys):
    f = tmp_path/"y.txt"; f.write_text("hello", encoding="utf-8")
    import ai_rpa.mailguard.detector as detector
    monkeypatch.setattr(detector, "detect", lambda text, headers=None: {"verdict":"ALLOW","score":0.1,"reasons":[]})
    rc = _run(["prog","--tasks","spamcheck","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert "spamcheck" in j["results"]  # 別名被正規化但結果鍵仍是 spamcheck
    assert j["results"]["spamcheck"]["verdict"] == "ALLOW"
