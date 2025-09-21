import os
from ai_rpa import scraper as sm

def test_scraper_offline_safe(monkeypatch):
    monkeypatch.setenv("OFFLINE","1")
    assert sm.scrape("http://stub.local") == []
