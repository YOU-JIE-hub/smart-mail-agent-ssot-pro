#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, random, re, os
from pathlib import Path

R = random.Random(20250830)

ENVS = ["prod","production","prd","staging","stage","stg","uat","test","dev"]
CURS = ["NT$", "USD", "US$", "$", "＄"]

def r_amount():
    base = R.choice([580, 1200, 5000, 12800, 34560, 90000, 105000])
    # 小數 / 千分位 / 全形逗號
    val = base + R.randint(-50, 50)
    s = f"{val:,}"
    if R.random() < 0.3: s = s.replace(",", "，")
    if R.random() < 0.25: s = s + f".{R.randint(1,99):02d}"
    cur = R.choice(CURS)
    # 少量全形數字
    if R.random() < 0.1:
        trans = str.maketrans("0123456789", "０１２３４５６７８９")
        s = s.translate(trans)
    return f"{cur}{s}"

def r_date():
    y = R.choice([2024, 2025])
    m = R.randint(1,12)
    d = R.randint(1,28)
    style = R.choice(["ymd_slash","ymd_dash","ymd_dot","md","zh_full","zh_md"])
    if style=="ymd_slash": return f"{y}/{m:02d}/{d:02d}"
    if style=="ymd_dash":  return f"{y}-{m:02d}-{d:02d}"
    if style=="ymd_dot":   return f"{y}.{m:02d}.{d:02d}"
    if style=="md":        return f"{m}/{d}"
    if style=="zh_full":   return f"{y}年{m}月{d}日"
    return f"{m}月{d}日"

def r_env():
    return R.choice(ENVS)

def r_sla_phrase():
    choices = [
        "SLA", "RTO", "RPO", "EOD", "EOW",
        "服務等級協議", "回應時間", "復原點目標"
    ]
    return R.choice(choices)

def make_sentence(intent):
    amt = r_amount()
    dt  = r_date()
    env = r_env()
    sla = r_sla_phrase()
    # 多樣模板
    if intent=="biz_quote":
        base = R.choice([
            f"請問 {dt} 前能提供正式報價？預估 {R.randint(5,80)} 位，預算約 {amt}。",
            f"想在 {dt} 前完成採購比價，能否先給報價單？目標金額 {amt}。"
        ])
        if R.random()<0.2: base += f" 另外希望於EOW內完成簽核（{R.choice(['EOW','EOD'])}）。"
        return base
    if intent=="complaint":
        return R.choice([
            f"我們對上次支援流程不滿，{dt} 已提交投訴單，請回覆處置。",
            f"{dt} 服務中斷超過 30 分鐘，請依 {r_sla_phrase()} 提供補償方案。"
        ])
    if intent=="tech_support":
        return R.choice([
            f"{env} 無法登入，自 {dt} 起持續異常，錯誤碼 401。",
            f"{dt} 部署後，{env} API 回傳 5xx，請協助排查。"
        ])
    if intent=="policy_qa":
        return R.choice([
            f"想了解 API 使用政策與資安規範，是否有 {sla} 相關文件？",
            f"請提供{sla}標準與外部稽核證明（若有），謝謝。"
        ])
    if intent=="profile_update":
        return R.choice([
            "請協助更新公司聯絡資訊與發票抬頭，本周內完成即可。",
            "變更寄送地址與統編資訊，完成後請回覆。"
        ])
    # other
    s = R.choice([
        "想索取產品簡介與 SDK 下載連結，謝謝。",
        "想了解教育方案與導入案例，煩請提供。"
    ])
    # 偶爾帶金額/日期噪聲
    if R.random()<0.15: s += f" 參考預算 {amt}。"
    if R.random()<0.15: s += f" 希望 {dt} 前回覆。"
    return s

def build_inbox(n=240):
    intents = ["biz_quote","complaint","tech_support","policy_qa","profile_update","other"]
    per = max(1, n // len(intents))
    rows=[]
    for it in intents:
        for _ in range(per):
            rows.append({"text": make_sentence(it)})
    R.shuffle(rows)
    return rows[:n]

# ==== 自動標註（優先使用你的 ruleset） ====
def compile_rules():
    # 內建與你規則等價的備援
    pat_amount = r"(?:NT\$|USD|US\$|\$|＄)\s?[0-9０-９][0-9０-９,，]*(?:[\.．][0-9０-９]+)?"
    pat_date = r"(?:\b[12][0-9]{3}[./-][0-9]{1,2}[./-][0-9]{1,2}\b|\b[0-9]{1,2}/[0-9]{1,2}\b|\b[12][0-9]{3}年[0-9]{1,2}月[0-9]{1,2}日\b|\b[0-9]{1,2}月[0-9]{1,2}日\b)"
    pat_env  = r"\b(prod|production|prd|staging|stage|stg|uat|test|dev)\b"
    pat_sla  = r"\b(SLA|RTO|RPO|EOD|EOW)\b|服務等級協議|回應時間|復原點目標"

    rx = {
        "amount": re.compile(pat_amount),
        "date_time": re.compile(pat_date),
        "env": re.compile(pat_env, re.I),
        "sla": re.compile(pat_sla, re.I),
    }
    return rx

def spans_by_rules(t, rx):
    spans=[]
    for label, rgx in rx.items():
        for m in rgx.finditer(t):
            spans.append({"start": m.start(), "end": m.end(), "label": label})
    return spans

def main():
    inbox_path = Path("data/real/inbox.jsonl")
    gold_path  = Path("data/kie/test_real.jsonl")
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) 產生去識別郵件
    rows = build_inbox(n=240)
    with inbox_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"text": r["text"]}, ensure_ascii=False) + "\n")

    # 2) 用規則自動標註
    rx = compile_rules()
    with gold_path.open("w", encoding="utf-8") as fo:
        for r in rows[:300]:  # 如需 200–300，這裡先寫 240 全量
            t = r["text"]; spans = spans_by_rules(t, rx)
            fo.write(json.dumps({"text": t, "spans": spans}, ensure_ascii=False) + "\n")

    # 3) 簡報統計
    cnt = {"amount":0,"date_time":0,"env":0,"sla":0}
    for r in rows:
        s = spans_by_rules(r["text"], rx)
        labs = {x["label"] for x in s}
        for k in cnt: cnt[k] += (1 if k in labs else 0)

    print("[OK] inbox->", inbox_path, " lines=", len(rows))
    print("[OK] gold ->", gold_path,  " lines=", len(rows))
    print("[COVER] per-field presence:", cnt)
if __name__ == "__main__":
    main()
