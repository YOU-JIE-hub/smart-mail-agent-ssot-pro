import sys

from ai_rpa.main import main


def test_main_errors_each_step(monkeypatch, tmp_path):
    import ai_rpa.file_classifier as fc
    import ai_rpa.nlp as nlp
    import ai_rpa.ocr as ocr
    import ai_rpa.scraper as scraper

    monkeypatch.setattr(
        ocr, "run_ocr", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ocr err"))
    )
    monkeypatch.setattr(
        scraper, "scrape", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("scrape err"))
    )
    monkeypatch.setattr(
        fc, "classify_dir", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cls err"))
    )
    monkeypatch.setattr(
        nlp, "analyze_text", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nlp err"))
    )

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
    assert rc == 0  # 不中斷，錯誤將被累積到 out["errors"]


def test_main_uses_config_tasks(monkeypatch, tmp_path):
    # 避免對外連線
    import ai_rpa.scraper as scraper

    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag": "h1", "text": "X"}])

    argv = ["prog"]  # 不提供 --tasks，走 YAML config 的既定 tasks
    monkeypatch.setattr(sys, "argv", argv)
    rc = main()
    assert rc == 0
