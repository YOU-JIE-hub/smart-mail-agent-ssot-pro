import os, re, pathlib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

SAFE_PAT = re.compile(r'[<>:"/\\|?*\x00-\x1F]+')

def safe_filename(name: str, limit: int = 150) -> str:
    if not isinstance(name, str):
        name = str(name)
    name = SAFE_PAT.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:limit]).rstrip("._")

def ensure_dir(p: str) -> str:
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)
    return p

def build_minimal_eml(subject: str, body: str, from_addr="no-reply@smart-mail.local",
                      to_addr="customer@example.com", message_id: str | None = None) -> bytes:
    em = EmailMessage()
    em["From"] = from_addr
    em["To"] = to_addr
    em["Subject"] = subject
    em["Date"] = formatdate(localtime=True)
    em["Message-ID"] = message_id or make_msgid(domain="localdomain")
    em.set_content(body or "")
    return em.as_bytes()

def write_bytes(path: str, data: bytes) -> str:
    ensure_dir(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(data)
    return path
