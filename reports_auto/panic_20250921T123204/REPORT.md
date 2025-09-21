# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import json, pathlib
root = pathlib.Path(".")
j = json.loads((root/"reports_auto/summary.json").read_text("utf-8"))

lines = []
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")

def section(name):
    m = j.get(name, {})
    lines.append("## " + name.upper() + "\n")
    if m.get("status") != "ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n")
        return
    if name != "kie":
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + json.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met = m.get("metrics", {})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    else:
        files = m.get("files", {})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")

for k in ("intent","spam","kie"):
    section(k)

outdir = root/"reports_auto/eval"
outdir.mkdir(parents=True, exist_ok=True)
(outdir/"summary.md").write_text("".join(lines), encoding="utf-8")
print("[OK] wrote", outdir/"summary.md")
PY
- LOG  : reports_auto/panic_20250921T123204/run.log
- ERR  : reports_auto/panic_20250921T123204/run.err
- PY   : reports_auto/panic_20250921T123204/python_stderr.txt
- OOM  : reports_auto/panic_20250921T123204/oom.txt
- TRACE: reports_auto/panic_20250921T123204/xtrace.sh
- SYS  : reports_auto/panic_20250921T123204/system.txt

## Heuristics
