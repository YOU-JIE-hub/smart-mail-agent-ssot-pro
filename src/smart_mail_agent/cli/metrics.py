import glob
import json
import time

from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server

from smart_mail_agent.utils.config import paths


def load_actions():
    P = paths()
    files = sorted(glob.glob(str(P.status / "ACTIONS_*.jsonl")))
    last = files[-1] if files else None
    if not last:
        return []
    out = []
    with open(last, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            out.append(json.loads(line))
    return out


def main():
    reg = CollectorRegistry()
    c = Counter("sma_actions_total", "actions by intent/status", ["intent", "status"], registry=reg)
    h = Histogram(
        "sma_action_latency_ms", "latency ms", ["intent"], registry=reg, buckets=(50, 100, 200, 400, 800, 1600, 3200)
    )
    Counter("sma_errors_total", "errors by phase", ["phase"], registry=reg)
    start_http_server(9108, registry=reg)
    while True:
        acts = load_actions()
        for a in acts:
            intent = (a.get("intent") or {}).get("intent") or a.get("intent")
            c.labels(intent=intent, status=a.get("status")).inc()
            if "latency_ms" in a:
                h.labels(intent=intent).observe(float(a["latency_ms"]))
        time.sleep(10)


if __name__ == "__main__":
    main()
