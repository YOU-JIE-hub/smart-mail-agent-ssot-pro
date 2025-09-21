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

def test_spam_task_records_steps(tmp_path, monkeypatch, capsys):
    f = tmp_path/"s.txt"; f.write_text("you are a WINNER click here", encoding="utf-8")
    monkeypatch.setenv("OFFLINE","1")
    rc = _run(["prog","--tasks","spam","--input-path",str(f)])
    assert rc == 0
    j = _read(capsys)
    assert j["results"]["spam"]["label"] in ("spam","ham")
    assert any(s.startswith("spam:") for s in j["steps"])
