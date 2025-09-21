from __future__ import annotations
import sys, json
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def _out(capsys): return json.loads(capsys.readouterr().out.strip())

def test_spam_only_via_main(tmp_path, monkeypatch, capsys):
    # 用 monkeypatch 控制 adapter 輸出
    import ai_rpa.spam_adapter as spam_adapter
    monkeypatch.setattr(spam_adapter, "score", lambda texts: {"label":"spam","score":0.9})
    f = tmp_path/"x.txt"; f.write_text("free money", encoding="utf-8")
    rc = _run(["prog","--tasks","spam","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert j["results"]["spam"]["label"] == "spam"
    assert any(s.startswith("spam:") for s in j["steps"])

def test_spam_with_nlp_pipeline(tmp_path, monkeypatch, capsys):
    import ai_rpa.spam_adapter as spam_adapter
    monkeypatch.setattr(spam_adapter, "score", lambda texts: {"label":"ham","score":0.1})
    f = tmp_path/"x.txt"; f.write_text("想要合作，請提供報價", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,spam","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert "nlp" in j["results"]
    assert "spam" in j["results"]
