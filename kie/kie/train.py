from __future__ import annotations
import argparse, json, pathlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing", default=None, help="已訓練 HF 權重目錄（若只要打包現有）")
    ap.add_argument("--outdir",   default="models/kie/artifacts/v1")
    args = ap.parse_args()

    out = pathlib.Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    if args.existing:
        # 只拷貝 meta（不搬大檔），並產出簡要報告
        (out / "training_report.json").write_text(json.dumps({"note":"using existing weights","src":args.existing}, ensure_ascii=False, indent=2), "utf-8")
        print(f"[OK] recorded existing -> {out}")
    else:
        (out / "training_report.json").write_text(json.dumps({"note":"TODO: fine-tune with labeled fields"}, ensure_ascii=False, indent=2), "utf-8")
        print(f"[OK] placeholder -> {out}")

if __name__=="__main__":
    main()
