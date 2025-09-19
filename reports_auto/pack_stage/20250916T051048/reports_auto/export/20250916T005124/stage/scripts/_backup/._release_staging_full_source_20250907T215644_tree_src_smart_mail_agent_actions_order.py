from typing import Any

from .utils.common import write_text


def handle(mail: dict[str, Any], kie: dict[str, Any]) -> dict[str, Any]:
    po = (kie.get("fields") or {}).get("po_no") or (kie.get("fields") or {}).get("order_id") or mail.get("id")
    md = f"# Order Acknowledgement\n\n- po_no: {po}\n- note: 已建立訂單草稿（示範）\n"
    path = write_text(f"order_ack_{po}.md", md)
    return {"ok": True, "artifacts": [path]}
