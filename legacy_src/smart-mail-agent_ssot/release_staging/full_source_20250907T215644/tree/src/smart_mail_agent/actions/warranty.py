from typing import Any

from .utils.common import write_text


def handle(mail: dict[str, Any], kie: dict[str, Any]) -> dict[str, Any]:
    rma = (kie.get("fields") or {}).get("rma_no") or f"RMA-{mail.get('id')}"
    md = f"# RMA Ticket\n- rma_no: {rma}\n- status: open\n"
    path = write_text(f"rma_{rma}.md", md)
    return {"ok": True, "artifacts": [path]}
