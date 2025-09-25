import json, sys

def _run(argv):
    from ai_rpa.main import main
    old = list(sys.argv)
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_main_unknown_task_stdout_contract(tmp_path, capsys):
    f = tmp_path/"t.txt"; f.write_text("hello", encoding="utf-8")
    rc = _run(["prog","--tasks","spamcheck,unknown","--input-path",str(f),"--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    assert j["tasks"] == ["spamcheck","unknown"]
    assert any("unknown task: unknown" in e for e in j.get("errors", []))
    assert isinstance(j.get("results", {}), dict)
    assert isinstance(j.get("steps", []), list)
