from ai_rpa.scraper import scrape


class DummyResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_scrape_monkeypatch(monkeypatch):
    html = "<html><h1>T1</h1><h2>T2</h2><p>x</p></html>"
    monkeypatch.setattr("requests.get", lambda url, timeout=10: DummyResp(html))
    out = scrape("http://x")
    assert {"tag": "h1", "text": "T1"} in out and {"tag": "h2", "text": "T2"} in out
