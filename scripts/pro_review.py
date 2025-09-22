from pathlib import Path
base = Path("reports_auto/pro/latest")
print("=== review (intent errors, head 15) ===")
p = base/"errors_intent.tsv"
if p.exists():
    for i,ln in enumerate(p.read_text("utf-8",errors="ignore").splitlines()):
        if i>=15: break
        print(ln)
else:
    print("(missing)", p)
print("\n=== review (spam errors, head 15) ===")
p = base/"errors_spam.tsv"
if p.exists():
    for i,ln in enumerate(p.read_text("utf-8",errors="ignore").splitlines()):
        if i>=15: break
        print(ln)
else:
    print("(missing)", p)
print("\n=== charts ===")
for n in ["cm_intent.png","cm_spam.png","reliability_spam.png","summary_panel.png"]:
    q = base/n
    if q.exists(): print(q)
