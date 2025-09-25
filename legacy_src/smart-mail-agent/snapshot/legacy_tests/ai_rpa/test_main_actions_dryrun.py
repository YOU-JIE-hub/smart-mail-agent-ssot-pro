import sys

from ai_rpa.main import main


def test_main_actions_dryrun(monkeypatch, tmp_path):
    # 避免對外連線
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
        "--dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = main()
    assert rc == 0
    assert not outp.exists()  # dry-run 不應落地
