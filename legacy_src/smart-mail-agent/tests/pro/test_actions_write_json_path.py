from pathlib import Path
from ai_rpa import actions as actions_mod
import json

def test_write_json_serializes_path(tmp_path):
    outp = tmp_path/"x.json"
    actions_mod.write_json({"p": tmp_path}, outp)
    j = json.loads(outp.read_text(encoding="utf-8"))
    assert isinstance(j.get("p",""), str) and j["p"].endswith(str(tmp_path.name))
