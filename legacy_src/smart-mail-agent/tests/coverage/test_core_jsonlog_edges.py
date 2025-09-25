from __future__ import annotations
from pathlib import Path
from smart_mail_agent.core.utils import jsonlog as J

def test_jsonlog_empty_and_bad_lines(tmp_path):
    p = tmp_path / "m.jsonl"
    p.write_text("\nnot-json\n{\"ok\":1}\n", encoding="utf-8")
    rows = list(J.read_jsonl(p))
    assert rows == [{"ok":1}]
    rows2 = J.parse_jsonl(p)
    assert rows2 == [{"ok":1}]
