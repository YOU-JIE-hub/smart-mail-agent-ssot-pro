from pathlib import Path
from ai_rpa import actions as actions_mod
import json

class Foo:  # 觸發 default 的未知型別
    def __repr__(self) -> str:
        return "<Foo>"

def test_write_json_with_str_path_and_custom_type(tmp_path):
    outp = tmp_path/"out.json"
    payload = {"p": tmp_path, "foo": Foo()}
    actions_mod.write_json(payload, str(outp))
    j = json.loads(outp.read_text(encoding="utf-8"))
    assert isinstance(j.get("p",""), str) and j["p"].endswith(tmp_path.name)
    assert isinstance(j.get("foo",""), str)


from pathlib import Path
from ai_rpa import actions as actions_mod
import json

class Bar:
    def __repr__(self) -> str:
        return "<Bar>"

def test_write_json_path_target(tmp_path):
    outp = tmp_path/"out2.json"
    payload = {"nested": {"x": tmp_path}, "bar": Bar()}
    actions_mod.write_json(payload, outp)  # 直接給 Path
    j = json.loads(outp.read_text(encoding="utf-8"))
    assert isinstance(j["nested"]["x"], str) and j["bar"]
