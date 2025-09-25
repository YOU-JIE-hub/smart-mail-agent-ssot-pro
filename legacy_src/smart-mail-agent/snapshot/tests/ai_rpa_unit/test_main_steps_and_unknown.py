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

def test_unknown_task_kept_and_steps_present(tmp_path, capsys):
    infile = tmp_path / "t.txt"
    infile.write_text("單純做 NLP 測試", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,unknown,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    # 任務列表保留 unknown；steps 一定存在；actions 正常執行但可能回空
    assert j["tasks"] == ["nlp","unknown","actions"]
    assert "steps" in j and any(s.startswith("nlp:") for s in j["steps"])
    assert "actions" in j["results"]
