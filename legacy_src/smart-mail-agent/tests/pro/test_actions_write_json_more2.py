from pathlib import Path
import json
from ai_rpa import actions as actions_mod

def test_write_json_str_target_and_non_jsonables(tmp_path):
    outp = tmp_path/"out3.json"
    payload = {
        "b": b"\x00\x01",
        "s": {1,2,3},   # 允許 json_safe 轉成字串或列表
        "p": tmp_path,  # Path 應可被轉為字串
    }
    actions_mod.write_json(payload, str(outp))  # 以字串路徑測另一條分支
    j = json.loads(outp.read_text(encoding="utf-8"))
    assert isinstance(j["b"], (str, list))
    assert isinstance(j["s"], (list, str))
    assert isinstance(j["p"], str)
