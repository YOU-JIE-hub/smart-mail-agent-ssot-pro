from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json, os, time
from tools.pipeline_baseline import load_contract, classify_rule, extract_slots_rule, plan_actions, run_pipeline

class Handler(BaseHTTPRequestHandler):
    def _json(self, code:int, obj):
        data=json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length","0"))
        raw = self.rfile.read(length) if length>0 else b"{}"
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json(400, {"error":"bad json"})
        contract = load_contract()
        if self.path == "/classify":
            intent = classify_rule(req, contract)
            return self._json(200, {"intent":intent})
        if self.path == "/extract":
            intent = req.get("intent") or classify_rule(req, contract)
            slots = extract_slots_rule(req, intent)
            return self._json(200, {"intent":intent,"slots":slots})
        if self.path == "/plan":
            intent = req.get("intent") or classify_rule(req, contract)
            slots = req.get("slots") or extract_slots_rule(req, intent)
            actions = plan_actions(intent, slots)
            return self._json(200, {"intent":intent,"actions":actions})
        if self.path == "/ingest_email":
            ts = time.strftime("%Y%m%dT%H%M%S")
            out = run_pipeline(req, ts)
            return self._json(200, out)
        return self._json(404, {"error":"not found"})

def main():
    host = os.environ.get("SMA_API_HOST","127.0.0.1")
    port = int(os.environ.get("SMA_API_PORT","8088"))
    httpd = HTTPServer((host,port), Handler)
    print(f"[API] http://{host}:{port}  (POST /classify /extract /plan /ingest_email)")
    httpd.serve_forever()

if __name__=="__main__":
    main()
