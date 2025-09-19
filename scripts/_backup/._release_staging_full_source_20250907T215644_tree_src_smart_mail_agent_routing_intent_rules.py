# -*- coding: utf-8 -*-
import re, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
CFG  = ROOT / "configs" / "intent_rules.yml"
_DEFAULT = {
  "priority": ["投訴","報價","技術支援","規則詢問","資料異動","其他"],
  "patterns": {
    "投訴": r"(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)",
    "報價": r"(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)",
    "技術支援": r"(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)",
    "規則詢問": r"(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)",
    "資料異動": r"(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)",
    "其他": r".*"
  }
}
def _load_yaml_or_json_text(txt: str):
  try:
    import yaml
    return yaml.safe_load(txt)
  except Exception:
    try:
      return json.loads(txt)
    except Exception:
      return None
def load_rules(cfg_path=CFG):
  obj = None
  if cfg_path.exists():
    try:
      obj = _load_yaml_or_json_text(cfg_path.read_text(encoding="utf-8"))
    except Exception:
      obj = None
  if not obj: obj = _DEFAULT
  prio = obj.get("priority", _DEFAULT["priority"])
  pats = {k: re.compile(v, re.I) for k, v in obj.get("patterns", _DEFAULT["patterns"]).items()}
  return prio, pats
