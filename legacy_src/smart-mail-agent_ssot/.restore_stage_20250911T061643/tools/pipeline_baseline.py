from __future__ import annotations
import json, time, os, re
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(os.environ.get("ROOT") or Path.cwd())

def load_contract() -> Dict[str,Any]:
    p = ROOT/"artifacts_prod/intent_contract.json"
    return json.loads(p.read_text(encoding="utf-8"))

def classify_rule(email: Dict[str,Any], contract: Dict[str,Any]) -> str:
    # 簡單規則：主旨含 [名稱] 或 內文含名稱關鍵字
    subject = email.get("subject","")
    body    = email.get("body","")
    for it in contract.get("intents", []):
        name = it.get("name","")
        tag  = it.get("subject_tag","")
        if tag and tag in subject:
            return name
        # 關鍵詞弱匹配
        if name and (name in subject or name in body):
            return name
    return "一般回覆"

def extract_slots_rule(email: Dict[str,Any], intent: str) -> Dict[str,Any]:
    # 範例：抓單價/數量/單號等常見欄位（沒有就留空）
    slots = {}
    text = f"{email.get('subject','')}\n{email.get('body','')}"
    m = re.search(r"(?:單價|price)[:：]\s*([0-9]+)", text)
    if m: slots["price"] = int(m.group(1))
    m = re.search(r"(?:數量|qty)[:：]\s*([0-9]+)", text)
    if m: slots["qty"] = int(m.group(1))
    m = re.search(r"(?:單號|order|ticket)[:：]\s*([A-Za-z0-9\-]+)", text)
    if m: slots["order_id"] = m.group(1)
    return slots

def plan_actions(intent: str, slots: Dict[str,Any]) -> List[Dict[str,Any]]:
    # 依意圖規劃多種企業常見動作（不只寄信）
    if intent == "報價":
        return [{"type":"create_quote","payload":slots},
                {"type":"reply_email","template":"quote_reply"}]
    if intent == "投訴":
        return [{"type":"create_ticket","priority":"high"},
                {"type":"escalate","to":"qa_manager"},
                {"type":"reply_email","template":"complaint_ack"}]
    if intent == "技術支援":
        return [{"type":"create_ticket","priority":"normal"},
                {"type":"attach_kb","article":"kb_troubleshoot_101"},
                {"type":"reply_email","template":"support_triage"}]
    if intent == "規則詢問":
        return [{"type":"reply_email","template":"policy_answer"},
                {"type":"log_audit","topic":"policy"}]
    if intent == "資料異動":
        return [{"type":"update_crm","fields":slots or {"op":"pending"}},
                {"type":"reply_email","template":"change_ack"}]
    # 一般回覆 / fallback
    return [{"type":"reply_email","template":"general_reply"}]

def exec_actions(intent: str, actions: List[Dict[str,Any]], run_ts: str) -> None:
    out_dir = ROOT/"reports_auto/actions"/run_ts
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, act in enumerate(actions, 1):
        # 寫成 .json 當作 RPA 執行紀錄；未來可換成真正 webhook/DB/工單 API
        (out_dir/f"{i:02d}_{act['type']}.json").write_text(
            json.dumps({"intent":intent,"action":act,"ts":time.time()}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

def run_pipeline(email: Dict[str,Any], run_ts: str) -> Dict[str,Any]:
    contract = load_contract()
    t0 = time.time()
    intent = classify_rule(email, contract)
    t1 = time.time()
    slots  = extract_slots_rule(email, intent)
    t2 = time.time()
    actions = plan_actions(intent, slots)
    t3 = time.time()
    exec_actions(intent, actions, run_ts)
    return {
        "intent": intent,
        "slots": slots,
        "actions": actions,
        "latency_ms": {
            "classify": int((t1-t0)*1000),
            "extract":  int((t2-t1)*1000),
            "plan":     int((t3-t2)*1000),
        }
    }

if __name__ == "__main__":
    # 小型 smoke：stdin 輸入 email json
    import sys
    email = json.loads(sys.stdin.read())
    ts = time.strftime("%Y%m%dT%H%M%S")
    print(json.dumps(run_pipeline(email, ts), ensure_ascii=False, indent=2))
