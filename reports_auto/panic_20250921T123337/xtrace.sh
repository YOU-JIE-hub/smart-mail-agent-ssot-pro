+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\''
import json, pathlib
root=pathlib.Path(".")
j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[]
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")
def section(name):
    m=j.get(name,{})
    lines.append("## " + name.upper() + "\n")
    if m.get("status")!="ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n")
        return
    if name!="kie":
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + json.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met=m.get("metrics",{})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    else:
        files=m.get("files",{})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")
for k in ("intent","spam","kie"):
    section(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\''
import json, pathlib
root=pathlib.Path(".")
j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[]
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")
def section(name):
    m=j.get(name,{})
    lines.append("## " + name.upper() + "\n")
    if m.get("status")!="ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n")
        return
    if name!="kie":
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + json.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met=m.get("metrics",{})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    else:
        files=m.get("files",{})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")
for k in ("intent","spam","kie"):
    section(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY' ']'
+ echo '== SNAPSHOT 20250921T123337 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT|SPAM|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc '. .venv/bin/activate; python3 - <<'\''PY'\''
import json, pathlib
root=pathlib.Path(".")
j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[]
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")
def section(name):
    m=j.get(name,{})
    lines.append("## " + name.upper() + "\n")
    if m.get("status")!="ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n")
        return
    if name!="kie":
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + json.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met=m.get("metrics",{})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    else:
        files=m.get("files",{})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")
for k in ("intent","spam","kie"):
    section(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY'
++ tee -a reports_auto/panic_20250921T123337/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<'\''PY'\''
import json, pathlib
root=pathlib.Path(".")
j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[]
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")
def section(name):
    m=j.get(name,{})
    lines.append("## " + name.upper() + "\n")
    if m.get("status")!="ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n")
        return
    if name!="kie":
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + json.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met=m.get("metrics",{})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    else:
        files=m.get("files",{})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")
for k in ("intent","spam","kie"):
    section(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY'
+ echo '- LOG  : reports_auto/panic_20250921T123337/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T123337/run.err'
+ echo '- PY   : reports_auto/panic_20250921T123337/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T123337/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T123337/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T123337/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T123337/run.err reports_auto/panic_20250921T123337/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T123337/run.err reports_auto/panic_20250921T123337/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T123337/run.err reports_auto/panic_20250921T123337/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T123337/run.err reports_auto/panic_20250921T123337/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T123337/REPORT.md\nreports_auto/panic_20250921T123337/run.log\nreports_auto/panic_20250921T123337/run.err\nreports_auto/panic_20250921T123337/python_stderr.txt\nreports_auto/panic_20250921T123337/xtrace.sh\nreports_auto/panic_20250921T123337/system.txt\nreports_auto/panic_20250921T123337/oom.txt\n'
+ exit 0
