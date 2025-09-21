import sys

from ai_rpa.main import main


def test_main_ocr_empty_text(monkeypatch, tmp_path):
    import ai_rpa.file_classifier as fc
    import ai_rpa.ocr as ocr
    import ai_rpa.scraper as scraper

    # OCR 有結果但 text 為空
    monkeypatch.setattr(ocr, "run_ocr", lambda p: {"path": str(p), "text": ""})
    # Scrape 產生一個有效標題
    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag": "h1", "text": "合作"}])
    # 分類回空集合
    monkeypatch.setattr(
        fc, "classify_dir", lambda p: {"image": [], "pdf": [], "text": [], "other": []}
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
    assert rc == 0
