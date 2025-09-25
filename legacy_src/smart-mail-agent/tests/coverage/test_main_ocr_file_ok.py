import json, sys
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

def test_ocr_on_file_success(tmp_path, capsys, monkeypatch):
    # 讓 OCR 成功且有 text
    import ai_rpa.ocr as ocr
    monkeypatch.setattr(ocr, "run_ocr", lambda p: {"path": str(p), "text": "掃到字囉"})

    f = tmp_path/"img.png"; f.write_bytes(b"\x89PNG")  # 佔位檔案
    rc = _run(["prog","--tasks","ocr","--input-path",str(f)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    assert "ocr" in j["results"]
    assert j["results"]["ocr"]["text"] == "掃到字囉"
    # steps 有 ocr 執行痕跡
    assert any("ocr" in s for s in j.get("steps",[]))
