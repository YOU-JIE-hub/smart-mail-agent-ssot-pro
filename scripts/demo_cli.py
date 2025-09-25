import os, json, pathlib, importlib, time, asyncio
import httpx
from scripts.rpa.router import route
from scripts.rpa.actions import adapters
from scripts.policy.engine import explain as rule_explain

def _import_asgi():
    app_import=os.getenv("APP","sma.api.service_compat:app")
    mod, attr = app_import.split(":")
    return getattr(importlib.import_module(mod), attr)

async def _predict_intent_async(app, text:str)->tuple[str,dict]:
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            r=await client.post("/v1/predict/intent", json={"text":text})
            if r.status_code>=400:
                return None, {"status":r.status_code,"body":r.text}
            data=r.json()
            intent = data.get("label") or (data.get("labels") or [None])[0] or "other"
            return intent, {"status":r.status_code,"body":data}
        except Exception as e:
            return None, {"exc":repr(e)}

async def main_async(src="data/probe/intent_eval.jsonl"):
    app=_import_asgi()
    ts=time.strftime('%Y%m%dT%H%M%S')
    outdir=pathlib.Path(f"reports_auto/actions/{ts}"); outdir.mkdir(parents=True, exist_ok=True)
    errlog=(outdir/"errors.log")

    p=pathlib.Path(src)
    if not p.exists():
        (outdir/"README.txt").write_text("No data/probe/intent_eval.jsonl; created empty run.", encoding="utf-8")
        print("OUT:", outdir); return

    for i,ln in enumerate(p.read_text(encoding="utf-8",errors="ignore").splitlines()):
        if not ln.strip(): continue
        row=json.loads(ln); text=row.get("text","")
        intent, meta = await _predict_intent_async(app, text)

        if intent is None:
            # 後備：規則引擎
            rule = rule_explain(text)
            intent = rule.get("intent_hint","other")
            errlog.write_text((errlog.read_text(encoding="utf-8") if errlog.exists() else "") +
                              f"[{ts} #{i}] API 失敗，改用規則推斷 intent={intent}，細節={json.dumps(meta,ensure_ascii=False)}\n",
                              encoding="utf-8")

        for act in route(intent):
            fn=getattr(adapters, act); fn(intent, text)

    print("OUT:", outdir)

if __name__=="__main__":
    asyncio.run(main_async())
