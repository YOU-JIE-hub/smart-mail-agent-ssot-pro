import json
import sys

from ai_rpa.main import main


def test_cli_main_with_actions(monkeypatch, tmp_path):
    # 避免外部連線
    import ai_rpa.scraper as scraper

    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag": "h1", "text": "T"}])

    outp = tmp_path / "out.json"
    argv = [
        "prog",
        "--tasks",
        "ocr,scrape,classify_files,nlp,actions",
        "--input-path",
        str(tmp_path),
        "--url",
        "http://stub.local",
        "--output",
        str(outp),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = main()
    assert rc == 0
    data = json.loads(outp.read_text(encoding="utf-8"))
    assert "steps" in data and any("nlp" in step for step in data["steps"])
