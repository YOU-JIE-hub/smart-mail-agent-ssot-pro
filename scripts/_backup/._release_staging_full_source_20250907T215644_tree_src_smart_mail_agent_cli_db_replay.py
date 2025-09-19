import argparse
import json
import sqlite3

from smart_mail_agent.actions.router import route
from smart_mail_agent.ml import infer
from smart_mail_agent.utils.config import paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    db = sqlite3.connect(paths().reports / "sma.sqlite3")
    rows = db.execute(
        "SELECT idem, payload FROM dead_letters ORDER BY created_at DESC LIMIT ?", (args.limit,)
    ).fetchall()
    for idem, payload in rows:
        obj = json.loads(payload)
        mail = {"id": obj.get("id"), "subject": None, "sender": None, "body": obj.get("body", "")}
        it = infer.predict_intent(mail["body"])
        kie = infer.extract_kie(mail["body"])
        r = route(mail, it.get("intent"), kie)
        print(
            json.dumps(
                {"idem": idem, "replayed": True, "intent": it.get("intent"), "artifacts": r.get("artifacts")},
                ensure_ascii=False,
            )
        )
    db.close()


if __name__ == "__main__":
    main()
