import json, sys
from pathlib import Path

def _run(argv):
    from ai_rpa.main import main
    import sys as _sys
    old = list(_sys.argv)
    try:
        _sys.argv = argv
        return main()
    finally:
        _sys.argv = old

def test_spamcheck_only_allow(tmp_path, capsys, monkeypatch):
    # 避免真正打外部：讓 mailguard 檢測直接回 ALLOW
    import ai_rpa.mailguard.detector as detector
    monkeypatch.setattr(detector, "detect",
                        lambda text, headers=None: {"verdict":"ALLOW","score":0.05,"reasons":[]})

    f = tmp_path/"mail.txt"; f.write_text("一般敘述", encoding="utf-8")
    rc = _run(["prog","--tasks","spamcheck","--input-path",str(f)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    # 結果鍵名應為 spamcheck（即使別名是 mailguard）
    assert "spamcheck" in j["results"]
    assert j["results"]["spamcheck"]["verdict"] in ("ALLOW","HAM")
    # steps 至少應記錄 spam/spamcheck 被執行
    assert any("spam" in s or "spamcheck" in s for s in j.get("steps",[]))
