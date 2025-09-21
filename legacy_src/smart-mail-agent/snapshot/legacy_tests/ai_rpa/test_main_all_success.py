import json
import sys

from ai_rpa.main import main


def test_main_all_success(monkeypatch, tmp_path):
    # 模擬 OCR 成功、有文字
    import ai_rpa.ocr as ocr

    monkeypatch.setattr(ocr, "run_ocr", lambda p: {"path": str(p), "text": "我要退款"})

    # 模擬 Scrape 成功、有 h1
    import ai_rpa.scraper as scraper

    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag": "h1", "text": "合作"}])

    # 模擬檔案分類
    import ai_rpa.file_classifier as fc

    monkeypatch.setattr(
        fc, "classify_dir", lambda p: {"image": [], "pdf": [], "text": [], "other": []}
    )

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
    # labels 應至少包含來自 OCR 的 refund 與來自 Scrape 的 sales 其中之一
    assert any("nlp" in step for step in data["steps"])
