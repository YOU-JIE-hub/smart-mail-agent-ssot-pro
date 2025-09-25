from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, os
from pipeline_baseline import run_pipeline

HOST, PORT = "127.0.0.1", 8088

class H(BaseHTTPRequestHandler):
    def _json(self, code:int, obj):
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    def do_POST(self):
        ln = int(self.headers.get("Content-Length","0")); data = self.rfile.read(ln) if ln>0 else b"{}"
        try:
            req = json.loads(data or b"{}")
        except Exception as e:
            return self._json(400, {"error": f"bad json: {e}"})
        if self.path in ("/classify","/extract","/plan","/e2e"):
            res = run_pipeline({"subject":req.get("subject",""), "body":req.get("body","")}, backend=os.environ.get("BACKEND","rule"))
            if self.path == "/classify":   return self._json(200, {"intent": res["intent"]})
            if self.path == "/extract":    return self._json(200, {"slots":  res["slots"]})
            if self.path == "/plan":       return self._json(200, res["plan"])
            if self.path == "/e2e":        return self._json(200, res)
        self._json(404, {"error": "not found"})
    def log_message(self, fmt, *args): pass

if __name__ == "__main__":
    print(f"[API] Serving on http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), H).serve_forever()
