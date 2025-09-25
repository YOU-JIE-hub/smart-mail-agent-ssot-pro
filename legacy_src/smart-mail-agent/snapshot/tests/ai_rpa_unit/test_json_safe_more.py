from __future__ import annotations
from dataclasses import dataclass
from ai_rpa.utils.json_safe import jsonable

class X:  # fallback 類型
    def __repr__(self) -> str:
        return "<X obj>"

@dataclass
class D:
    a: int

def test_jsonable_fallback_and_nested():
    data = {
        "none": None,
        "bool": True,
        "tuple": (1, 2),
        "set": {3, 1, 2},
        "map": {"k": {9, 8}},
        "obj": X(),
        "dc": D(7),
        "exc": ValueError("bad"),
    }
    j = jsonable(data)
    # tuple -> list
    assert j["tuple"] == [1, 2]
    # set -> list（順序不保證，做包含檢查）
    assert sorted(j["set"]) in ([1,2,3], ["1","2","3"])
    # 巢狀 map + set
    inner = j["map"]["k"]
    assert sorted(inner) in ([8,9], ["8","9"])
    # fallback 物件 -> 可列印字串
    assert isinstance(j["obj"], str) and "X obj" in j["obj"]
    # dataclass -> dict
    assert j["dc"]["a"] == 7
    # 例外 -> 類名: 訊息
    assert "ValueError: bad" in j["exc"]
