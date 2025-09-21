import importlib
import os

from smart_mail_agent.core.utils import jsonlog as core_jsonlog
from smart_mail_agent.utils import logger as pkg_logger

os.environ.setdefault("SMA_LOG_LEVEL", "DEBUG")


def test_logger_module_proxy():
    importlib.reload(pkg_logger)
    lg = pkg_logger.get_logger("boost")
    lg.debug("ok")
    assert lg.name == "boost" or lg.name.endswith(".boost")


def test_jsonlog_dump_and_parse(tmp_path):
    data = {"a": 1, "b": "x"}
    p = tmp_path / "a.jsonl"
    core_jsonlog.dump_jsonl([data], p)
    rows = list(core_jsonlog.read_jsonl(p))
    assert rows and rows[0]["a"] == 1


def test_policy_engine_shim():
    from smart_mail_agent import policy_engine

    assert hasattr(policy_engine, "apply_policies")
