import sys
from pathlib import Path

def test_dry_run_does_not_write(tmp_path, monkeypatch):
    # 避免對外連線
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag": "h1", "text": "T"}])

    from ai_rpa.main import main

    outp = tmp_path / "out.json"
    argv = [
        "prog",
        "--tasks", "ocr,scrape,classify_files,nlp,actions",
        "--input-path", str(tmp_path),
        "--url", "http://stub.local",
        "--output", str(outp),
        "--dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setenv("OFFLINE", "1")

    rc = main()
    assert rc == 0
    assert not outp.exists(), "dry-run 應該不會落地寫檔"
