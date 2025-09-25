from __future__ import annotations

from smart_mail_agent.sma_types import normalize_result


def test_normalize_result_branches():
    raw = {
        "action_name": "reply_general",
        "subject": "您好",
        "attachments": ["a.txt", None, {"name": "b.pdf", "size": 123}],
    }
    res = normalize_result(raw)
    try:
        data = res.model_dump()
    except Exception:
        data = res.dict()
    assert data["action"] == "reply_general"
    assert data["subject"].startswith("[自動回覆] ")
    assert isinstance(data["attachments"], list)
    assert data.get("duration_ms", 0) == 0
