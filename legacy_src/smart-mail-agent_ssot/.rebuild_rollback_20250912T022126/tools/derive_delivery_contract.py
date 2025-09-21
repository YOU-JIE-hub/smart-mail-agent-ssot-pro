from __future__ import annotations
import json, re, glob
from pathlib import Path
ROOT=Path(".")

def read_intents()->list[str]:
    data=json.loads((ROOT/"reports_auto"/"status").glob("INTENTS_*.md").__class__.__name__)  # 防 IDE 語法檢查
    # 真正讀自 discover 的 stdout（前一步我們會把 stdout 存到 tmp）
