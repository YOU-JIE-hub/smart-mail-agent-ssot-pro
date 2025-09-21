+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\''
import json, pathlib
root=pathlib.Path("."); j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[f"# Smart Mail Agent — 煙霧測試摘要（{j[created_at]}）\n"]
def add(model):
    m=j[model]; lines.append(f"## {model.upper()}\n")
    if m.get("status")!="ok":
        lines.append(f"- 狀態：{m.get(status)}  \n- 錯誤：{m.get(error)}\n"); return
    if model!="kie":
        lines.append(f"- 範例數：{m[n]}  \n- 模型：`{m[model_path]}`  \n- classes：{m[classes_]}\n")
        lines.append(f"- 準確率：{m[metrics].get(accuracy,0):.3f}  \n- Macro-F1：{m[metrics].get(macro_f1,0):.3f}\n")
    else:
        lines.append(f"- 目錄：`{m.get(dir,)}`  \n- 狀態：ok  \n- 必要檔：config.json / model.safetensors / tokenizer.json\n")
for k in ("intent","spam","kie"): add(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("\n".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\''
import json, pathlib
root=pathlib.Path("."); j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[f"# Smart Mail Agent — 煙霧測試摘要（{j[created_at]}）\n"]
def add(model):
    m=j[model]; lines.append(f"## {model.upper()}\n")
    if m.get("status")!="ok":
        lines.append(f"- 狀態：{m.get(status)}  \n- 錯誤：{m.get(error)}\n"); return
    if model!="kie":
        lines.append(f"- 範例數：{m[n]}  \n- 模型：`{m[model_path]}`  \n- classes：{m[classes_]}\n")
        lines.append(f"- 準確率：{m[metrics].get(accuracy,0):.3f}  \n- Macro-F1：{m[metrics].get(macro_f1,0):.3f}\n")
    else:
        lines.append(f"- 目錄：`{m.get(dir,)}`  \n- 狀態：ok  \n- 必要檔：config.json / model.safetensors / tokenizer.json\n")
for k in ("intent","spam","kie"): add(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("\n".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY' ']'
+ echo '== SNAPSHOT 20250921T122845 =='
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
root=pathlib.Path("."); j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[f"# Smart Mail Agent — 煙霧測試摘要（{j[created_at]}）\n"]
def add(model):
    m=j[model]; lines.append(f"## {model.upper()}\n")
    if m.get("status")!="ok":
        lines.append(f"- 狀態：{m.get(status)}  \n- 錯誤：{m.get(error)}\n"); return
    if model!="kie":
        lines.append(f"- 範例數：{m[n]}  \n- 模型：`{m[model_path]}`  \n- classes：{m[classes_]}\n")
        lines.append(f"- 準確率：{m[metrics].get(accuracy,0):.3f}  \n- Macro-F1：{m[metrics].get(macro_f1,0):.3f}\n")
    else:
        lines.append(f"- 目錄：`{m.get(dir,)}`  \n- 狀態：ok  \n- 必要檔：config.json / model.safetensors / tokenizer.json\n")
for k in ("intent","spam","kie"): add(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("\n".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY'
++ tee -a reports_auto/panic_20250921T122845/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<'\''PY'\''
import json, pathlib
root=pathlib.Path("."); j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[f"# Smart Mail Agent — 煙霧測試摘要（{j[created_at]}）\n"]
def add(model):
    m=j[model]; lines.append(f"## {model.upper()}\n")
    if m.get("status")!="ok":
        lines.append(f"- 狀態：{m.get(status)}  \n- 錯誤：{m.get(error)}\n"); return
    if model!="kie":
        lines.append(f"- 範例數：{m[n]}  \n- 模型：`{m[model_path]}`  \n- classes：{m[classes_]}\n")
        lines.append(f"- 準確率：{m[metrics].get(accuracy,0):.3f}  \n- Macro-F1：{m[metrics].get(macro_f1,0):.3f}\n")
    else:
        lines.append(f"- 目錄：`{m.get(dir,)}`  \n- 狀態：ok  \n- 必要檔：config.json / model.safetensors / tokenizer.json\n")
for k in ("intent","spam","kie"): add(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("\n".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
PY'
+ echo '- LOG  : reports_auto/panic_20250921T122845/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T122845/run.err'
+ echo '- PY   : reports_auto/panic_20250921T122845/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T122845/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T122845/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T122845/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T122845/run.err reports_auto/panic_20250921T122845/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T122845/run.err reports_auto/panic_20250921T122845/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T122845/run.err reports_auto/panic_20250921T122845/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T122845/run.err reports_auto/panic_20250921T122845/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T122845/REPORT.md\nreports_auto/panic_20250921T122845/run.log\nreports_auto/panic_20250921T122845/run.err\nreports_auto/panic_20250921T122845/python_stderr.txt\nreports_auto/panic_20250921T122845/xtrace.sh\nreports_auto/panic_20250921T122845/system.txt\nreports_auto/panic_20250921T122845/oom.txt\n'
+ exit 1
