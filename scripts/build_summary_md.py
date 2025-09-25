import json, pathlib
root=pathlib.Path(".")
j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[]
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")
def sec(name):
    m=j.get(name,{})
    lines.append("## " + name.upper() + "\n")
    if m.get("status")!="ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n"); return
    if name!="kie":
        import json as _j
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + _j.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met=m.get("metrics",{})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    else:
        import json as _j
        files=m.get("files",{})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + _j.dumps(files, ensure_ascii=False) + "\n")
for k in ("intent","spam","kie"): sec(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
