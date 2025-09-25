from typing import Any

from .utils.common import write_text


def handle(mail: dict[str, Any], kie: dict[str, Any]) -> dict[str, Any]:
    f = kie.get("fields") or {}
    title, vat = f.get("invoice_title"), f.get("vat")
    needs = not (title and vat)
    md = ["# Invoice Request", f"- title: {title}", f"- vat: {vat}", f"- needs_review: {needs}"]
    path = write_text(f"invoice_req_{mail.get('id')}.md", "\n".join(md))
    return {"ok": True, "artifacts": [path], "needs_review": needs}
