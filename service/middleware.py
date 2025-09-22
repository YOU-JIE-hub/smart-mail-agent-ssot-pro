import time, uuid
from typing import Callable
from fastapi import Request, Response

def request_id() -> str:
    return uuid.uuid4().hex[:12]

async def timing_middleware(request: Request, call_next: Callable):
    start = time.perf_counter()
    rid = request.headers.get("x-request-id") or request_id()
    try:
        response: Response = await call_next(request)
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        try:
            response.headers["x-request-id"] = rid
            response.headers["x-latency-ms"] = f"{elapsed:.2f}"
        except Exception:
            pass
    return response
