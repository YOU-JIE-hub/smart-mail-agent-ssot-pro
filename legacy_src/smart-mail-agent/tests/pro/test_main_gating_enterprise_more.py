import json, os
from pathlib import Path
from ai_rpa.main import main as cli_main

def _run(argv):
    import sys
    old = list(sys.argv)
    try:
        sys.argv = argv
        return cli_main()
    finally:
        sys.argv = old

def _stdout_json(capsys):
    out = capsys.readouterr().out.strip()
    assert out.startswith("{") and out.endswith("}")
    return json.loads(out)

def test_allow_runs_actions(tmp_path, capsys):
    f = tmp_path/"ok.txt"; f.write_text("想合作 需要方案與報價", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f)])
    assert rc == 0
    j = _stdout_json(capsys)
    assert j["results"]["spamcheck"]["verdict"] == "ALLOW"
    assert isinstance(j["results"].get("actions", []), list) and j["results"]["actions"]

def test_block_skips_actions(tmp_path, capsys):
    f = tmp_path/"bad.txt"; f.write_text("free money!!!", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f)])
    assert rc == 0
    j = _stdout_json(capsys)
    assert j["results"]["spamcheck"]["verdict"] == "BLOCK"
    # BLOCK: 不產生 actions 結果
    assert "actions" not in j["results"]

def test_exec_flag_produces_exec_section(tmp_path, capsys, monkeypatch):
    f = tmp_path/"ok2.txt"; f.write_text("想洽談合作與報價", encoding="utf-8")
    os.environ["SMA_OUTBOX"] = str(tmp_path/"outbox")
    os.environ["SMA_WORKDIR"] = str(tmp_path/"work")
    os.environ["SMA_DB"] = str(tmp_path/"db.sqlite")
    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(f),"--exec"])
    assert rc == 0
    j = _stdout_json(capsys)
    # 只要 --exec，結果中會包含 exec（每個步驟的執行結果）
    assert "exec" in j["results"]
