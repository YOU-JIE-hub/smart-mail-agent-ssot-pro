import importlib
import pkgutil

import pytest

import smart_mail_agent

# 自動發現 smart_mail_agent 下面的所有可匯入模組（避免手寫重覆清單）
mods = [
    m.name for m in pkgutil.walk_packages(smart_mail_agent.__path__, prefix="smart_mail_agent.")
]


@pytest.mark.parametrize("mod", mods)
def test_import_module(mod: str) -> None:
    importlib.import_module(mod)
