from __future__ import annotations

import importlib
import logging

import smart_mail_agent.utils.logger as logger


def test_get_logger_and_level(monkeypatch, caplog):
    monkeypatch.setenv("SMA_LOG_LEVEL", "DEBUG")
    importlib.reload(logger)
    caplog.set_level(logging.DEBUG)
    lg = logger.get_logger("sma.test")
    lg.debug("hello debug")
    assert any("hello debug" in rec.message for rec in caplog.records)
    before = len(lg.handlers)
    lg2 = logger.get_logger("sma.test")
    assert len(lg2.handlers) == before
