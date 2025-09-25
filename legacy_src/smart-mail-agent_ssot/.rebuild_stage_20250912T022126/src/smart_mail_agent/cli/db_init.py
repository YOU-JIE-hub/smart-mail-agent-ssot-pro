from __future__ import annotations

import json

from smart_mail_agent.utils.config import paths


def main() -> int:
    p = paths()
    print(json.dumps({"ok": True, "paths": str(p.reports)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
