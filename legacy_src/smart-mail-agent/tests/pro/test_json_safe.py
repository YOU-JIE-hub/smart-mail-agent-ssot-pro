import json
from pathlib import Path
from ai_rpa.utils.json_safe import to_jsonable

def test_path_and_set_serialization(tmp_path):
    obj = {"p": tmp_path, "s": {"b","a"}}
    js = json.dumps(to_jsonable(obj), ensure_ascii=False)
    assert js and js.startswith("{")
