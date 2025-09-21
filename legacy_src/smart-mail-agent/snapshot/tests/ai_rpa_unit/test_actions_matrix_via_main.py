from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def _read_stdout(capsys):
    out = capsys.readouterr().out.strip()
    assert out, "應該有 stdout JSON"
    return json.loads(out)

def test_actions_sales_only(tmp_path, monkeypatch, capsys):
    # 文本只會產生銷售意圖（關鍵詞：合作）
    infile = tmp_path / "sales.txt"
    infile.write_text("想要合作、請提供方案", encoding="utf-8")

    # 避免外連：scraper 回空
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    assert isinstance(acts, list) and len(acts) >= 1
    assert any("quote" in str(a).lower() or "sales" in str(a).lower() for a in acts)

def test_actions_support_only(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "support.txt"
    infile.write_text("發票錯了 想退款", encoding="utf-8")

    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    assert isinstance(acts, list) and len(acts) >= 1
    assert any("support" in str(a).lower() or "reply" in str(a).lower() for a in acts)

def test_actions_none(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "none.txt"
    infile.write_text("隨意的敘述，無關鍵字", encoding="utf-8")

    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    assert isinstance(acts, list) and len(acts) == 0

def test_actions_dry_run(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "dry.txt"
    infile.write_text("需要客服協助 退款", encoding="utf-8")

    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local","--dry-run"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    # 乾跑：應仍回傳規劃，但不做外部副作用；不強制鍵名，只檢查型別與數量
    assert isinstance(acts, list) and len(acts) >= 1
