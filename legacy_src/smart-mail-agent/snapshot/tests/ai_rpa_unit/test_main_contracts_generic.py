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

def _stdout_json(capsys):
    out = capsys.readouterr().out.strip()
    assert out, "應該有 stdout JSON"
    return json.loads(out)

def test_contract_always_has_steps(monkeypatch, tmp_path, capsys):
    # monkeypatch 掉 scraper，避免外連
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [{"tag":"h1","text":"T"}])
    infile = tmp_path / "t.txt"
    infile.write_text("合作與退款", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,actions,scrape","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _stdout_json(capsys)
    assert "steps" in j and isinstance(j["steps"], list)
    assert "results" in j and "nlp" in j["results"] and "actions" in j["results"]

def test_unknown_task_ignored_but_logged(monkeypatch, tmp_path, capsys):
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])
    rc = _run(["prog","--tasks","abc,nlp","--input-path",str(tmp_path/"x.txt"),"--url","u"])
    assert rc == 0
    j = _stdout_json(capsys)
    assert any("unknown task: abc" in e for e in j.get("errors", []))
    assert "nlp:ok" in j.get("steps", [])

def test_task_alias_normalization(monkeypatch, tmp_path, capsys):
    # "classify" 會被正規化成 classify_files
    p = tmp_path; (p/"a.jpg").write_bytes(b"\x00"); (p/"b.pdf").write_bytes(b"%PDF"); (p/"c.txt").write_text("t","utf-8")
    rc = _run(["prog","--tasks","classify","--input-path",str(p)])
    assert rc == 0
    j = _stdout_json(capsys)
    cls = j.get("results",{}).get("classify",{})
    assert set(cls.keys()) >= {"image","pdf","text","other"}
