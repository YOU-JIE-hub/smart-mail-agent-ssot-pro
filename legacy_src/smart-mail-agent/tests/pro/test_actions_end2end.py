import json
from pathlib import Path

def _run(argv):
    import sys
    from ai_rpa.main import main
    old = list(sys.argv)
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def _stdout_json(capsys):
    return json.loads(capsys.readouterr().out.strip())

def test_actions_refund(tmp_path, capsys):
    f = tmp_path/"t.txt"; f.write_text("我要退款 發票錯了", encoding="utf-8")
    _ = _run(["prog","--tasks","nlp,actions","--input-path",str(f)])
    j = _stdout_json(capsys)
    assert isinstance(j["results"].get("actions", []), list)

def test_actions_sales_with_scrape_context(tmp_path, monkeypatch, capsys):
    f = tmp_path/"t.txt"; f.write_text("合作與導入", encoding="utf-8")
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag":"h1","text":"方案與價格"}])
    _ = _run(["prog","--tasks","nlp,scrape,actions","--input-path",str(f),"--url","http://stub.local"])
    j = _stdout_json(capsys)
    acts = j["results"].get("actions", [])
    assert any(s.get("id")=="context" for s in acts)
