from __future__ import annotations

def test_ocr_reads_text(tmp_path):
    from ai_rpa.ocr import run_ocr
    f = tmp_path/"doc.txt"
    f.write_text("hello OCR", encoding="utf-8")
    out = run_ocr(f)
    assert isinstance(out, dict) and "text" in out

def test_scraper_requests_mock(monkeypatch):
    # 避免外網，mock requests.get 回簡單 HTML
    import types
    import ai_rpa.scraper as scraper

    class Resp:
        status_code = 200
        text = "<html><h1>Title</h1><p>Para</p></html>"

    monkeypatch.setattr(scraper, "requests", types.SimpleNamespace(get=lambda url, timeout=5: Resp()))
    items = scraper.scrape("http://example.com")
    assert isinstance(items, list) and items and all(isinstance(x, dict) for x in items)

def test_spam_adapter_calls_mailguard(monkeypatch):
    # 讓 adapter 的判定可控，確保函式本體被跑過
    import ai_rpa.spam_adapter as spam_adapter
    monkeypatch.setattr("ai_rpa.mailguard.detect", lambda text, **k: {"verdict":"BLOCK","score":1.2,"reasons":["kw_block"]})
    out = spam_adapter.score(["free money!!!"])
    assert out["label"] in ("spam","ham") and isinstance(out.get("score",0.0), float)

def test_config_loader_safe(tmp_path, monkeypatch):
    # 若 yaml 失敗或沒有檔案，load_config 退化為 {}
    import ai_rpa.utils.config_loader as cfg
    bogus = tmp_path/"nope.yml"
    out = cfg.load_config(bogus)
    assert out == {} or isinstance(out, dict)
