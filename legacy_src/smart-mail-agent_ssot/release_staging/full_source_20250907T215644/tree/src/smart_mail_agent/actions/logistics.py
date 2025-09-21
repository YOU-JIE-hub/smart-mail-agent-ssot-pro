from typing import Any

from .utils.common import write_text


def handle(mail: dict[str, Any], kie: dict[str, Any]) -> dict[str, Any]:
    trk = (kie.get("fields") or {}).get("tracking_no")
    if trk:
        md = f"# Shipping Notice\n- tracking_no: {trk}\n"
        path = write_text(f"shipping_{trk}.md", md)
        return {"ok": True, "artifacts": [path]}
    else:
        path = write_text(f"shipping_pending_{mail.get('id')}.md", "# Shipping Pending: 請補齊追蹤碼")
        return {"ok": True, "artifacts": [path], "needs_review": True}
