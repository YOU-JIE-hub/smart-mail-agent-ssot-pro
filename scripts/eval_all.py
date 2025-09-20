from __future__ import annotations
import subprocess as sp, sys, json, pathlib

def run(cmd: list[str]) -> dict:
    print("+", " ".join(cmd)); sys.stdout.flush()
    out = sp.check_output(cmd, text=True, stderr=sp.STDOUT)
    try:
        return json.loads(out)
    except Exception:
        return {"raw": out}

def main():
    pathlib.Path("reports_auto").mkdir(exist_ok=True)
    s = {}
    s["intent"] = run([sys.executable, "scripts/eval_intent.py"])
    s["spam"]   = run([sys.executable, "scripts/eval_spam.py"])
    s["kie"]    = run([sys.executable, "scripts/eval_kie.py"])
    (pathlib.Path("reports_auto")/"summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=2))

if __name__=="__main__":
    main()
