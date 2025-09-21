import sys

from ai_rpa.main import main


def test_cli_main_smoke(monkeypatch, tmp_path):
    # 避免外部 pytest 外掛干擾
    monkeypatch.setenv("PYTHONUTF8", "1")
    # 避免對外連線：替換 scraper.scrape
    import ai_rpa.scraper as scraper

    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag": "h1", "text": "T"}])
    argv = [
        "prog",
        "--tasks",
        "ocr,scrape,classify_files,nlp",
        "--input-path",
        str(tmp_path),
        "--url",
        "http://stub.local",
        "--dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = main()
    assert rc == 0
