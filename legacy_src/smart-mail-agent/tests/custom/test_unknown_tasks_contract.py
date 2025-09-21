import json, sys
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

def test_unknown_kept_and_logged(tmp_path, capsys, monkeypatch):
    f = tmp_path/"t.txt"; f.write_text("單純做 NLP 測試", encoding="utf-8")
    monkeypatch.setenv("OFFLINE","1")
    rc = _run(["prog","--tasks","abc,nlp,actions","--input-path",str(f)])
    assert rc == 0
    j = _read(capsys)
    assert j["tasks"] == ["abc","nlp","actions"]
    assert "abc" in j["unknown"]
    assert any("unknown task: abc" in e for e in j.get("errors", []))
