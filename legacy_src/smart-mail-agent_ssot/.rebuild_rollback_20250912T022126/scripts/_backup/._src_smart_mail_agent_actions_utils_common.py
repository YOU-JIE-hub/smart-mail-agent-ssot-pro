from smart_mail_agent.utils.config import paths


def write_text(rel: str, content: str) -> str:
    p = paths()
    out = p.status / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return str(out)
