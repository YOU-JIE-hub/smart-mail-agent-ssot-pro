from __future__ import annotations
from pathlib import Path
from smart_mail_agent.core.utils import jsonlog as jl

def test_parse_and_read_jsonl_with_bad_lines(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"a":1}\nnot-a-json\n{"b":2}\n', encoding="utf-8")

    rows = jl.parse_jsonl(p)
    assert len(rows) == 2 and rows[0]["a"] == 1 and rows[1]["b"] == 2

    rows2 = list(jl.read_jsonl(p))
    assert len(rows2) == 2 and rows2[0]["a"] == 1 and rows2[1]["b"] == 2
