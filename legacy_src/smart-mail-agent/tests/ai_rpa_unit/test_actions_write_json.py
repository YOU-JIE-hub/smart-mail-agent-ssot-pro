from __future__ import annotations
import json
from pathlib import Path
from ai_rpa.actions import write_json

def test_write_json_roundtrip(tmp_path):
    p = tmp_path / "act_out.json"
    obj = {"ok": True, "ints": ["sales","support"]}
    outp = write_json(obj, p)
    s = Path(outp).read_text(encoding="utf-8")
    j = json.loads(s)
    assert j == obj
