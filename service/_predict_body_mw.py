# -*- coding: utf-8 -*-
# ASGI middleware that rewrites POST /v1/predict body to {"text": ...} only.
import json, typing, datetime, pathlib, asyncio
from typing import Callable, Awaitable, Dict, Any

LOGD = pathlib.Path("reports_auto/serve/diag")
LOGD.mkdir(parents=True, exist_ok=True)

def _log(line: str) -> None:
    try:
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        with (LOGD / f"predict_body_rewrite.{ts}.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

class StripPredictExtras:
    """Buffer entire body; if path=/v1/predict & method=POST & json is dict with 'text',
       replace body with {'text': original['text']} to avoid normalize_text(**payload) signature errors.
    """
    def __init__(self, app: Callable[[Dict[str, Any], Callable, Callable], Awaitable[None]]):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") != "/v1/predict":
            return await self.app(scope, receive, send)

        # buffer the whole request body
        body_chunks = []
        more_body = True
        async def _recv():
            nonlocal more_body
            if more_body:
                msg = await receive()
                if msg["type"] == "http.request":
                    body_chunks.append(msg.get("body", b""))
                    more_body = msg.get("more_body", False)
                return msg
            return {"type": "http.request", "body": b"", "more_body": False}

        # drain
        while more_body:
            await _recv()

        raw = b"".join(body_chunks)
        new_body = raw
        try:
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict) and "text" in data:
                new_body = json.dumps({"text": data["text"]}, ensure_ascii=False).encode("utf-8")
                _log(f"[rewrite] kept only text (len_in={len(raw)}, len_out={len(new_body)})")
            else:
                _log(f"[pass] body not dict-with-text (len={len(raw)})")
        except Exception as e:
            _log(f"[pass] json decode failed: {e!r} (len={len(raw)})")

        # provide a new receive() that serves the rewritten body once
        served = False
        async def new_receive():
            nonlocal served
            if not served:
                served = True
                return {"type": "http.request", "body": new_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        # Optionally adjust content-length header (not strictly required)
        try:
            hdrs = []
            found = False
            for (k, v) in scope.get("headers", []):
                if k == b"content-length":
                    hdrs.append((k, str(len(new_body)).encode("utf-8"))); found = True
                else:
                    hdrs.append((k, v))
            if not found:
                hdrs.append((b"content-length", str(len(new_body)).encode("utf-8")))
            scope["headers"] = hdrs
        except Exception:
            pass

        return await self.app(scope, new_receive, send)
