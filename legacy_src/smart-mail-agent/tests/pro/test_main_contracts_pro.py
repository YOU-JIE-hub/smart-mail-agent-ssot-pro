import json, sys
from pathlib import Path

def _run(argv):
    import sys
    from ai_rpa.main import main
    old = list(sys.argv)
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_unknown_and_dry_run(tmp_path, capsys):
    outp = tmp_path/"out.json"
    rc = _run(["prog","--tasks","nlp,unknown,actions","--input-path",str(tmp_path/"t.txt"),"--output",str(outp),"--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    assert j["tasks"] == ["nlp","unknown","actions"]
    assert any("unknown task: unknown" in e for e in j.get("errors", []))
    assert not outp.exists()
