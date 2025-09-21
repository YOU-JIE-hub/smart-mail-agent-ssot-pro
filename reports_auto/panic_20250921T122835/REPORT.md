# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import pathlib, json
root=pathlib.Path(".")
(root/"data/intent_eval").mkdir(parents=True, exist_ok=True)
(root/"data/spam_eval").mkdir(parents=True, exist_ok=True)
intent=[{"text":"請提供合約報價與付款方式","label":"報價"},
        {"text":"APP 登入錯誤，請協助處理","label":"技術支援"},
        {"text":"我要投訴上次的客服態度","label":"投訴"},
        {"text":"如何申請退款？流程是什麼","label":"規則詢問"},
        {"text":"我需要修改聯絡電話與地址","label":"資料異動"},
        {"text":"你好，想了解一般資訊","label":"其他"}]
spam=[{"text":"Hello team, this is a normal inquiry about pricing.","label":0},
      {"text":"FREE $$$ CLICK HERE!!! limited offer http://spam","label":1}]
with (root/"data/intent_eval/test.jsonl").open("w",encoding="utf-8") as f:
    for r in intent: f.write(json.dumps(r, ensure_ascii=False)+"\n")
with (root/"data/spam_eval/test.jsonl").open("w",encoding="utf-8") as f:
    for r in spam: f.write(json.dumps(r, ensure_ascii=False)+"\n")
print("[OK] Minimal eval sets written.")
PY
- LOG  : reports_auto/panic_20250921T122835/run.log
- ERR  : reports_auto/panic_20250921T122835/run.err
- PY   : reports_auto/panic_20250921T122835/python_stderr.txt
- OOM  : reports_auto/panic_20250921T122835/oom.txt
- TRACE: reports_auto/panic_20250921T122835/xtrace.sh
- SYS  : reports_auto/panic_20250921T122835/system.txt

## Heuristics
