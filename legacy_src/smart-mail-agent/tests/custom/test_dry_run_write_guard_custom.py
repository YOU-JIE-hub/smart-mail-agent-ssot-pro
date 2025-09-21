import json, sys, os
from pathlib import Path
from ai_rpa.main import main
import ai_rpa.scraper as scraper

def _run(argv):
    old = list(sys.argv)
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_dry_run_no_file_write(tmp_path, monkeypatch):
    # 避免外連
    monkeypatch.setenv("OFFLINE","1")
    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag":"h1","text":"T"}])
    outp = tmp_path/"out.json"
    f = tmp_path/"in.txt"; f.write_text("需要客服協助 退款", encoding="utf-8")
    rc = _run(["prog","--tasks","ocr,scrape,classify_files,nlp,actions","--input-path",str(f),"--url","http://stub.local","--output",str(outp),"--dry-run"])
    assert rc == 0
    assert not outp.exists()
