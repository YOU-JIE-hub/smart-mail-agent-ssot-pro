from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from ai_rpa.utils.json_safe import jsonable

@dataclass
class Foo:
    p: Path
    xs: list

def test_jsonable_path_exception_dataclass():
    d = {"p": Path("/tmp/x"), "e": ValueError("bad"), "s": {1,2}, "foo": Foo(Path("y"), [Path("z")])}
    j = jsonable(d)
    assert j["p"] == "/tmp/x"
    assert "ValueError: bad" in j["e"]
    assert sorted(j["s"]) == ["1","2"] or sorted(j["s"]) == [1,2]  # 允許 set 轉 list & 字串化
    assert j["foo"]["p"] == "y"
    assert j["foo"]["xs"] == ["z"]
