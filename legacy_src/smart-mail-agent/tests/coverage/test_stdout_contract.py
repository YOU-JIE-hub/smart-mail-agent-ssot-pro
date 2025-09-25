import sys, json

def test_stdout_has_json_when_no_output(tmp_path, monkeypatch, capsys):
    # 避免對外連線
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda url: [{"tag": "h1", "text": "T"}])

    from ai_rpa.main import main

    argv = [
        "prog",
        "--tasks", "nlp,actions",
        "--input-path", str(tmp_path),
        "--dry-run",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setenv("OFFLINE", "1")

    rc = main()
    assert rc == 0

    out = capsys.readouterr().out.strip()
    assert out.startswith("{") and out.endswith("}"), "stdout 應該是 JSON 一行"
    json.loads(out)  # 解析不應該拋錯
