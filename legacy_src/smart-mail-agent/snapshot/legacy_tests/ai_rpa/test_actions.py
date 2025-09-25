from pathlib import Path

from ai_rpa.actions import write_json


def test_write_json(tmp_path):
    out_path = tmp_path / "out.json"
    ret = write_json({"ok": True, "n": 1}, str(out_path))
    assert Path(ret).exists()
    txt = out_path.read_text(encoding="utf-8")
    assert '"ok": true' in txt or '"ok": True' in txt
