# -*- coding: utf-8 -*-
import json, os, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

def _json(body, code=200): return code, {"Content-Type": "application/json"}, json.dumps(body, ensure_ascii=False).encode()

def _predict_rule_one(text: str) -> str:
    src = os.environ.get("SMA_RULES_SRC","")
    if src and Path(src).is_file():
        import importlib.util
        spec = importlib.util.spec_from_file_location("runtime_rules", src)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        if hasattr(m, "predict_one"):
            lab = m.predict_one(text)
            return lab if lab else "other"
    return "一般回覆"

_BUNDLE = None
try:
    from tools.model_bundle import IntentBundle
    bdir = os.environ.get("SMA_BUNDLE_DIR","bundles/intent_v1/LATEST")
    if Path(bdir).exists():
        _BUNDLE = IntentBundle(bdir); _BUNDLE.preflight()
except Exception:
    _BUNDLE = None

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        ln = int(self.headers.get("Content-Length","0") or 0)
        raw = self.rfile.read(ln).decode("utf-8") if ln else "{}"
        try: obj = json.loads(raw)
        except Exception: self._send(*_json({"error":"bad json"}, 400)); return

        if self.path == "/classify":
            route = (obj.get("route") or "rule").lower()
            texts = obj.get("texts") or []
            if not isinstance(texts, list): texts = [str(texts)]
            if route == "ml" and _BUNDLE:
                preds = _BUNDLE.predict(texts)
                self._send(*_json({"intent": preds[0] if preds else "other"})); return
            else:
                lab = _predict_rule_one(texts[0] if texts else "")
                self._send(*_json({"intent": lab})); return

        elif self.path == "/extract":
            txt = obj.get("text") or ""
            out = {"price": None, "qty": None, "id": None}
            m = (re.search(r'(?:\$|NTD?\s*)\s*([0-9][\d,\.]*)', txt, re.I)
                 or re.search(r'([0-9][\d,\.]*)\s*(?:元|NTD?|\$)', txt, re.I))
            if m: out["price"] = m.group(1).replace(",","")
            q = re.search(r'(?:數量|各|共|x)\s*([0-9]+)', txt, re.I)
            if q: out["qty"] = int(q.group(1))
            i = re.search(r'\b([A-Z]{2,}-?\d{4,})\b', txt)
            if i: out["id"] = i.group(1)
            self._send(*_json({"slots": out})); return

        elif self.path == "/plan":
            intent = obj.get("intent") or "其他"
            plan = {"action":"generic_reply","ok":True}
            if intent in ("biz_quote","報價"):
                plan = {"action":"create_quote_pdf","ok":True}
            self._send(*_json({"plan": plan})); return

        self._send(*_json({"error":"not found"}, 404))

    def log_message(self, fmt, *args): pass
    def _send(self, code, headers, body):
        self.send_response(code)
        for k,v in headers.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)

if __name__ == "__main__":
    port = int(os.environ.get("PORT","8088"))
    print(f"[API] http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
