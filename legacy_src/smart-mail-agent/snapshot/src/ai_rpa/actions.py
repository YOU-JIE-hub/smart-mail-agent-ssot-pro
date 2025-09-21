from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, List
from ai_rpa.utils.json_safe import jsonable

__all__ = ["plan_actions", "write_json"]

def plan_actions(intents: Iterable[str] | None, *, dry_run: bool = False) -> List[str]:
    intents_set = {str(x).strip().lower() for x in (intents or []) if str(x).strip()}
    sales_keys = {"sales", "quote", "合作", "商務", "報價"}
    support_keys = {"support", "refund", "客服", "退貨", "退款", "維修", "抱怨"}
    actions: List[str] = []
    if intents_set & support_keys:
        actions.append("reply_support")
    if intents_set & sales_keys:
        actions.append("send_quote")
    # 不對 dry_run 做特別處理，主程式決定是否落地
    # 去重保持順序
    seen, out = set(), []
    for a in actions:
        if a not in seen:
            seen.add(a); out.append(a)
    return out

def write_json(obj, path) -> str:
    """
    將 obj 以 JSON 寫入 path（可以是 str/Path）；回傳實際路徑字串。
    符合舊測試預期：write_json(obj, path)
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(jsonable(obj), ensure_ascii=False)
    p.write_text(payload, encoding="utf-8")
    return str(p)
