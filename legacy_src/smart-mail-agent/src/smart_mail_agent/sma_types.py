from __future__ import annotations

from typing import Any, List, Optional

# --- Prefer Pydantic v2; fallback to a tiny shim if not present ---
_HAS_PYDANTIC = True
try:
    from pydantic import BaseModel

    try:
        # v2
        from pydantic import ConfigDict, Field  # type: ignore
    except Exception:  # v1 fallback types
        from pydantic import Field  # type: ignore

        ConfigDict = dict  # type: ignore[assignment]
except Exception:
    _HAS_PYDANTIC = False


if _HAS_PYDANTIC:

    class Attachment(BaseModel):
        name: str
        size: Optional[int] = None

    class NormalizedResult(BaseModel):
        # v2 style; for v1 會被忽略
        try:
            model_config = ConfigDict(extra="allow")  # type: ignore[call-arg]
        except Exception:  # v1

            class Config:  # type: ignore[no-redef]
                extra = "allow"

        action_name: Optional[str] = None
        subject: Optional[str] = None
        attachments: List[Attachment] = Field(default_factory=list)

else:
    # Minimal shim to satisfy tests without pydantic
    class _Shim:
        def __init__(self, data: dict) -> None:
            self._data = dict(data)

        def model_dump(self) -> dict:
            return dict(self._data)

        def dict(self) -> dict:
            return dict(self._data)

        def __getitem__(self, k: str) -> Any:
            return self._data[k]

        def __getattr__(self, k: str) -> Any:
            try:
                return self._data[k]
            except KeyError as e:
                raise AttributeError(k) from e

    Attachment = dict  # type: ignore[assignment]

    class NormalizedResult(_Shim):  # type: ignore[misc]
        pass


def _norm_attachments(att: Any) -> list:
    out: list = []
    if isinstance(att, (list, tuple, set)):
        for a in att:
            if not a:
                continue
            if isinstance(a, str):
                if _HAS_PYDANTIC:
                    out.append(Attachment(name=a))
                else:
                    out.append({"name": a})
            elif isinstance(a, dict):
                name = str(a.get("name", "")).strip()
                if not name:
                    continue
                size = a.get("size", None)
                try:
                    size = int(size) if size is not None else None
                except Exception:
                    size = None
                if _HAS_PYDANTIC:
                    out.append(Attachment(name=name, size=size))
                else:
                    out.append({"name": name, "size": size})
            # 其他型別忽略
    return out


_REPLY_ACTION_HINTS = ("reply", "reply_", "auto_reply", "autoreply")
_EXISTING_REPLY_PREFIXES = (
    "[自動回覆]",
    "[自動回复]",
    "[Auto Reply]",
    "[AUTO REPLY]",
    "Re:",
    "RE:",
)


def _maybe_prefix_subject(subject: Any, action: Optional[str], action_name: Optional[str]) -> str:
    s = "" if subject is None else str(subject).strip()
    # 若判斷為回覆類動作，且尚未有任何已知回覆前綴，就加上 "[自動回覆] "
    act = (action or action_name or "").strip().lower()
    is_reply = any(h in act for h in _REPLY_ACTION_HINTS)
    if is_reply and s:
        ss = s.lstrip()
        if not any(ss.startswith(p) for p in _EXISTING_REPLY_PREFIXES):
            s = f"[自動回覆] {ss}"
        else:
            s = ss
    return s


def normalize_result(obj: Any) -> NormalizedResult:
    """
    把各種輸入（dict / Pydantic v1 model / v2 model）規整為
    - Pydantic v2 BaseModel（優先；允許 extra）
    - 或 shim 物件，且一定有 .model_dump() / .dict()
    並：
      * 正規化 attachments
      * 補齊 action / action_name 雙向別名
      * 對 reply* 類動作自動補 "[自動回覆] " 主旨前綴
    """
    # 拿到 dict 來源
    if isinstance(obj, dict):
        data = dict(obj)
    else:
        # 先試 v2
        md = getattr(obj, "model_dump", None)
        if callable(md):
            try:
                data = dict(md())
            except Exception:
                data = {}
        else:
            # 再試 v1
            d = getattr(obj, "dict", None)
            data = dict(d()) if callable(d) else {}

    data = {**data}

    # --- action / action_name 雙向別名 ---
    action = data.get("action")
    action_name = data.get("action_name")
    if action and not action_name:
        data["action_name"] = action
    elif action_name and not action:
        data["action"] = action_name

    # --- subject 規則（回覆前綴）---
    data["subject"] = _maybe_prefix_subject(
        data.get("subject"), data.get("action"), data.get("action_name")
    )

    # --- attachments 正規化 ---
    data["attachments"] = _norm_attachments(data.get("attachments"))

    if _HAS_PYDANTIC:
        return NormalizedResult(**data)
    return NormalizedResult(data)


# 兼容舊名稱
def normalize_extra_result(obj: Any) -> NormalizedResult:
    return normalize_result(obj)


# 舊名稱也有人用
normalize = normalize_result

__all__ = [
    "Attachment",
    "NormalizedResult",
    "normalize_result",
    "normalize_extra_result",
    "normalize",
]
