import json, sys
def _run(argv):
    from ai_rpa.main import main
    old = list(sys.argv)
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_allow_online_smoke(tmp_path, capsys, monkeypatch):
    f = tmp_path/"t.txt"; f.write_text("任意文字", encoding="utf-8")
    # 不設 OFFLINE，但帶 --allow-online，確認 JSON 骨架
    rc = _run(["prog","--input-path",str(f),"--allow-online"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    assert j.get("ok") is True
    assert isinstance(j.get("tasks",[]), list)
    assert isinstance(j.get("results",{}), dict)
    assert isinstance(j.get("unknown",[]), list)
    assert isinstance(j.get("steps",[]), list)
    assert isinstance(j.get("errors",[]), list)
