from ai_rpa.utils.logger import get_logger


def test_get_logger_idempotent():
    a = get_logger("X")
    b = get_logger("X")
    assert a is b
    a.info("hello")
