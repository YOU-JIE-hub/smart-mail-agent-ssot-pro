from __future__ import annotations
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sys
from tools.pipeline_baseline import load_contract, classify_rule, extract_slots_rule, plan_actions_rule
contract = load_contract()
class H(BaseHTTPRequestHandler):
    def _send(self, code:int, obj):
        body=json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        try:
            n=int(self.headers.get("Content-Length","0")); data=self.rfile.read(n)
            email=json.loads(data.decode("utf-8"))
            if   self.path=="/classify": self._send(200, {"intent": classify_rule(email, contract)})
            elif self.path=="/extract" : self._send(200, {"slots":  extract_slots_rule(email, email.get("intent") or classify_rule(email, contract))})
            elif self.path=="/plan"    :
                intent=email.get("intent") or classify_rule(email, contract)
                slots =email.get("slots")  or extract_slots_rule(email, intent)
                self._send(200, {"plan":   plan_actions_rule(intent, slots)})
            elif self.path=="/e2e":
                intent=classify_rule(email, contract); slots=extract_slots_rule(email, intent); plan=plan_actions_rule(intent, slots)
                self._send(200, {"intent":intent,"slots":slots,"plan":plan})
            else: self._send(404, {"error":"not found"})
        except Exception as e: self._send(500, {"error": str(e)})
if __name__=="__main__":
    port=int(sys.argv[1]) if len(sys.argv)>1 else 8088
    print(f"[API] http://127.0.0.1:{port}"); HTTPServer(("127.0.0.1", port), H).serve_forever()
