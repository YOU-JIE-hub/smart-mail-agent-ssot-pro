from ai_rpa import scraper as scraper_mod

def test_scrape_offline_returns_list(monkeypatch):
    monkeypatch.setenv("OFFLINE", "1")
    out = scraper_mod.scrape("http://stub.local")
    assert isinstance(out, list) and out == []
