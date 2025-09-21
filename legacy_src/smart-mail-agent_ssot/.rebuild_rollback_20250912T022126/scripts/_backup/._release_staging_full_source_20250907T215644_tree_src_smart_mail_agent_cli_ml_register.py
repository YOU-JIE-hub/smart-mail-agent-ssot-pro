import json
import zipfile

from smart_mail_agent.utils.config import paths


def main():
    P = paths()
    inbox = P.root / "artifacts_inbox"
    inbox.mkdir(exist_ok=True)
    out = {"ok": True, "registered": []}
    for z in sorted(inbox.glob("*.zip")):
        stem = z.stem
        dst = P.artifacts_store / stem
        dst.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z, "r") as zh:
            zh.extractall(dst)
        out["registered"].append({"zip": str(z), "to": str(dst)})
    (P.status / "REGISTER_LAST.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
