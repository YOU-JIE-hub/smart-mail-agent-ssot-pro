import os, re
from pathlib import Path
p=Path("scripts/env.default")
if p.exists():
    for line in p.read_text("utf-8").splitlines():
        m=re.match(r'export\s+([A-Z0-9_]+)=(.*)', line.strip())
        if m:
            k,v=m.group(1), m.group(2).strip().strip('"').strip("'")
            os.environ[k]=v
