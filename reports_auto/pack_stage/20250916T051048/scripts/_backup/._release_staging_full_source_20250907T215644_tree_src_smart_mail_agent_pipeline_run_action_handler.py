from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from smart_mail_agent.kie.infer import KIE
from smart_mail_agent.observability.audit_db import ensure_schema, write_err_log
from smart_mail_agent.spam.ens import SpamEnsemble

from .action_handler import plan_actions


def _now() -> int:
    return int(time.time())


def _safe(fn: Callable[[], Any], tag: str, mail_id: str) -> tuple[Any, str | None]:
    try:
        return fn(), None
    except Exception as e:
        write_err_log(tag, f"{mail_id}: {e.__class__.__name__}: {e}")
        return None, str(e)


def main(inbox_dir: str) -> None:
    ensure_schema()
    p = Path(inbox_dir)
    clf_spam = SpamEnsemble()
    clf_intent = None
    kie = KIE()
    cnt: Counter[str] = Counter()

    for fp in sorted(p.glob("*.txt")):
        mail_id = fp.stem
        text = fp.read_text(encoding="utf-8")

        y_spam = 0
        if clf_spam:
            y, err = _safe(lambda text=text: clf_spam.predict(text), "spam/predict", mail_id)
            y_spam = int(y == 1) if err is None else 0
        if y_spam == 1:
            cnt["spam"] += 1
            continue

        intent = "other"
        if clf_intent:
            lbl, err = _safe(lambda text=text: clf_intent.predict(text), "intent/predict", mail_id)
            intent = (lbl or "other") if err is None else "other"
        cnt[intent] += 1

        fields: dict[str, Any] = {}
        if kie:
            spans, _ = _safe(lambda text=text: kie.extract(text), "kie/extract", mail_id)
            if spans:
                fields["spans"] = spans

        plan_actions({"id": mail_id, "body": text}, {"intent": intent}, {"fields": fields})

    Path("reports_auto/status/INTENT_SUMMARY.json").write_text(
        json.dumps(cnt, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main("samples/inbox")
