from __future__ import annotations

import json

from smart_mail_agent.ingest.imap_pull import pull_and_enqueue

if __name__ == "__main__":
    print(json.dumps(pull_and_enqueue(), ensure_ascii=False))
