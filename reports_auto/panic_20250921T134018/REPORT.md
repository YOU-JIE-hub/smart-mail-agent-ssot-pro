# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import json, pathlib
root=pathlib.Path(".")
j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[]
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")

def sec_cls(name, title=None):
    m=j.get(name,{})
    lines.append("## " + (title or name.upper()) + "\n")
    if m.get("status")!="ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n")
        return
    if name!="kie":
        import json as _j
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + _j.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met=m.get("metrics",{})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
        th=m.get("thresholding")
        if th:
            rec=th.get("recommended",{})
            lines.append("- **建議閾值**：" + str(rec.get("threshold", rec.get("threshold", ""))) + "\n")
    else:
        files=m.get("files",{})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")
        inf=m.get("inference",{}); st=inf.get("sample_tensors",{})
        if st: lines.append("- Tensor 樣本形狀：" + json.dumps(st, ensure_ascii=False) + "\n")

sec_cls("intent","INTENT")
sec_cls("spam","SPAM")
sec_cls("kie","KIE")

out=root/"reports_auto/eval/summary.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(lines), "utf-8")
print("[OK] wrote", out)
PY
- LOG  : reports_auto/panic_20250921T134018/run.log
- ERR  : reports_auto/panic_20250921T134018/run.err
- PY   : reports_auto/panic_20250921T134018/python_stderr.txt
- OOM  : reports_auto/panic_20250921T134018/oom.txt
- TRACE: reports_auto/panic_20250921T134018/xtrace.sh
- SYS  : reports_auto/panic_20250921T134018/system.txt

## Heuristics
