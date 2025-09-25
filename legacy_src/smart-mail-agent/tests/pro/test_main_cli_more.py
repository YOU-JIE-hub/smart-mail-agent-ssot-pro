import json, sys
from pathlib import Path

def _run(argv):
    from ai_rpa.main import main
    old = list(sys.argv)
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_main_unknown_task_and_output(tmp_path):
    f = tmp_path/"t.txt"; f.write_text("hello", encoding="utf-8")
    outp = tmp_path/"out.json"
    rc = _run(["prog","--tasks","spamcheck,unknown","--input-path",str(f),"--output",str(outp)])
    assert rc == 0
    j = json.loads(outp.read_text(encoding="utf-8"))
    assert j["tasks"] == ["spamcheck","unknown"]
    assert any("unknown task: unknown" in e for e in j.get("errors", []))

def test_main_spam_alias_stdout(tmp_path, capsys):
    f = tmp_path/"t.txt"; f.write_text("hello", encoding="utf-8")
    rc = _run(["prog","--tasks","spamcheck","--input-path",str(f)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    assert "spamcheck" in j.get("results", {})
