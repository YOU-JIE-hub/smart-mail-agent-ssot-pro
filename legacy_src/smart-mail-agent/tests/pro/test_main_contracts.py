import json
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

def _out(capsys):
    return json.loads(capsys.readouterr().out.strip())

def test_cli_noop_and_alias(tmp_path, capsys):
    f = tmp_path/"t.txt"; f.write_text("hello", encoding="utf-8")
    rc = _run(["prog","--tasks","spamcheck,actions","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert "spamcheck" in j["results"]
    # alias spamcheck -> mailguard，但 tasks 保留原字串
    assert j["tasks"] == ["spamcheck","actions"]

def test_dry_run_write_guard(tmp_path, capsys):
    f = tmp_path/"t.txt"; f.write_text("合作 報價", encoding="utf-8")
    outp = tmp_path/"out.json"
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f),"--output",str(outp),"--dry-run"])
    assert rc == 0
    j = _out(capsys)
    assert not outp.exists()  # dry-run 不寫檔
    assert isinstance(j.get("steps",[]), list)
