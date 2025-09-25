from __future__ import annotations
import json, sys

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def test_classify_only_stdout(tmp_path, capsys):
    (tmp_path / "a.jpg").write_bytes(b"\x00")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.1")
    (tmp_path / "c.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "d.bin").write_bytes(b"\x00\x01")
    rc = _run(["prog","--tasks","classify_files","--input-path",str(tmp_path),"--url","http://stub.local"])
    assert rc == 0
    j = json.loads(capsys.readouterr().out.strip())
    cls = j.get("results", {}).get("classify", {})
    assert set(cls.keys()) >= {"image","pdf","text","other"}
