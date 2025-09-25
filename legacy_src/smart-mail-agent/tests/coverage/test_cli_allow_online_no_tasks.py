import os, sys, json
from pathlib import Path

def _run(argv):
    from ai_rpa.main import main
    import sys as _sys
    old = list(_sys.argv)
    try:
        _sys.argv = argv
        return main()
    finally:
        _sys.argv = old

def test_allow_online_no_tasks_stdout(tmp_path, capsys, monkeypatch):
    f = tmp_path/"t.txt"; f.write_text("隨便一行", encoding="utf-8")
    # 不設 OFFLINE，顯式帶 --allow-online 走另一支路
    rc = _run(["prog","--input-path",str(f),"--allow-online"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("{") and out.endswith("}")
    j = json.loads(out)
    # 合理的契約：至少有 ok/tasks/unknown/results/steps/errors 等骨架
    assert j.get("ok") is True
    assert isinstance(j.get("tasks",[]), list)
    assert isinstance(j.get("results",{}), dict)
    assert isinstance(j.get("unknown",[]), list)
    assert isinstance(j.get("steps",[]), list)
    assert isinstance(j.get("errors",[]), list)
