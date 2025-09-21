from __future__ import annotations
from pathlib import Path; import json, os

def safe_load(p:Path):
    if p.exists():
        try: return json.loads(p.read_text("utf-8"))
        except Exception: return None
    return None

def build_block():
    ens=safe_load(Path("artifacts_prod/ens_thresholds.json")) or {}
    intent=safe_load(Path("artifacts_prod/intent_rules_calib_v11c.json")) or {}
    kie=safe_load(Path("artifacts_prod/kie_runtime_config.json")) or {}
    lines=["## Model Thresholds & Rules",
           f"- spam.thresholds: `{ens.get('thresholds','(n/a)')}`" if isinstance(ens,dict) else f"- spam.thresholds: `(n/a)`",
           f"- intent.rules.version: `{intent.get('version','(n/a)')}`  items: `{len(intent.get('rules',[]))}`" if isinstance(intent,dict) else "- intent.rules: `(n/a)`",
           f"- kie.config.keys: `{','.join(sorted(kie.keys()))}`" if isinstance(kie,dict) else "- kie.config: `(n/a)`",
           ""]
    return "\n".join(lines)

def main():
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--run-dir", required=True)
    a=ap.parse_args()
    rd=Path(a.run_dir); sm=rd/"SUMMARY.md"
    base=sm.read_text("utf-8") if sm.exists() else "# SUMMARY\n"
    sm.write_text(base + "\n" + build_block(), "utf-8")
    print(f"[OK] appended thresholds block -> {sm}")
if __name__=="__main__":
    main()
