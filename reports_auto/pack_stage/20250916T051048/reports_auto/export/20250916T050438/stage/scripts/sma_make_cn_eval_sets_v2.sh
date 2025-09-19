#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
ROOT="/home/youjie/projects/smart-mail-agent_ssot"; cd "$ROOT"
log(){ printf '[%s] %s\n' "$(date +%F' '%T)" "$*"; }

SPAM_N="${SPAM_N:-150}"   # 每類 spam/ham 各 N（預設 150 -> 總 300）
KIE_N="${KIE_N:-50}"      # KIE 口語樣本數（可改 80/100）

mkdir -p data data/kie reports_auto

log "make Chinese spam eval (N_spam=$SPAM_N, N_ham=$SPAM_N) -> data/cn_spam_eval.jsonl"
python - <<'PY'
import json, random, pathlib
random.seed(20240904)
SPAM_N = int(__import__("os").environ.get("SPAM_N","150"))
HAM_N  = SPAM_N
urls   = ["https://fast-loan.xyz/apply","https://secure-reset.top/login","https://pay-invoice.shop/check",
          "https://account-verify.work/auth","https://wallet-cash.cam/refund","https://mydrive.zip/share"]

def mix(pieces):
    # 隨機插入全形標點/空格/時間語氣
    pad = random.choice(["","  ","　"])
    tone = random.choice(["請儘速","麻煩盡快","煩請","請於24小時內","請於48小時內","請立即"])
    return pad.join(pieces).replace("  ", " ").replace("　　","　").replace("{TONE}", tone)

spam_bank = [
  ("釣魚/驗證", [
    lambda: ( "【安全提醒】您的帳戶異常登入",
              mix(["我們偵測到風險登入，{TONE}點擊", random.choice(urls), "驗證身分，逾期將停用。"]) ),
    lambda: ( "重設密碼通知",
              mix(["為維護安全，請使用以下連結重設密碼：", random.choice(urls), "，若已處理請忽略。"]) ),
  ]),
  ("退款/罰款/海關", [
    lambda: ( "快遞清關：補交稅費",
              mix(["您的包裹待清關，需補交稅費，", "{TONE}", "完成：", random.choice(urls)]) ),
    lambda: ( "退款異常：請確認帳戶",
              mix(["您的退款遭退回，請在", random.choice(["24","48","72"]), "小時內於", random.choice(urls), "更新資料"]) ),
  ]),
  ("假冒客服/電商", [
    lambda: ( "訂單需要確認",
              mix(["我們無法配送您的訂單，請至", random.choice(urls), "更新地址與付款資訊"]) ),
    lambda: ( "付款失敗提醒",
              mix(["您最近的付款失敗，{TONE}完成驗證：", random.choice(urls)]) ),
  ]),
  ("雲端/共享檔案", [
    lambda: ( "新文件分享待查看",
              mix(["您收到一份共享文件，需登入以檢視：", random.choice(urls)]) ),
    lambda: ( "空間即將到期",
              mix(["您的雲端空間即將到期，為避免資料遺失，", "{TONE}", "前往：", random.choice(urls)]) ),
  ]),
  ("投資/貸款", [
    lambda: ( "本月專屬貸款利率",
              mix(["限時年利率", random.choice(["1.9%","2.2%"]), "，立即申請：", random.choice(urls)]) ),
    lambda: ( "USDT 理財升息",
              mix(["年化升至", random.choice(["12%","18%"]), "，{TONE}開通：", random.choice(urls)]) ),
  ]),
]

ham_bank = [
  ("內部通知", [
    lambda: ("[內部] 明早 10:00 例會",
             mix(["議程：進度/阻塞/風險，地點：會議室 A 或 Google Meet。"]) ),
    lambda: ("本週布署窗口與回報格式",
             mix(["請依 template 回報，若超時請先同步阻塞原因。"]) ),
  ]),
  ("客服往來", [
    lambda: ("回覆：上週單據補件",
             mix(["附件為補件掃描版，請查收；如需原件寄送，煩請回覆地址。"]) ),
    lambda: ("協助查詢票單狀態",
             mix(["工單 #", str(random.randint(1000,9999)), "，預計今晚 20:00 前回覆。"]) ),
  ]),
  ("採購合作", [
    lambda: ("詢價：年度續約與折扣",
             mix(["請提供 12+12 月方案與 SLA；同時回覆開立資訊。"]) ),
    lambda: ("到貨驗收與發票",
             mix(["設備已到貨，驗收正常；請於明日開立發票並寄出。"]) ),
  ]),
  ("技術支持", [
    lambda: ("API 金鑰失效排查",
             mix(["我們看到 401 error，請協助重發密鑰；如需線上 debug 可約時段。"]) ),
    lambda: ("沙箱環境流量上限",
             mix(["今晚 22:00 做壓測，請暫時調高上限；超過再回調。"]) ),
  ]),
]

def make_rows(bank, N, label):
    rows=[]
    for _ in range(N):
        g = random.choice(bank)[1]
        subj, body = random.choice(g)()
        rows.append({"id": f"{label}-{len(rows)+1:04d}", "subject": subj, "body": body, "attachments": [], "label": label})
    return rows

spam = make_rows(spam_bank, SPAM_N, "spam")
ham  = make_rows(ham_bank,  HAM_N,  "ham")

out = pathlib.Path("data/cn_spam_eval.jsonl")
with out.open("w", encoding="utf-8") as w:
    for r in spam + ham: w.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"[OK] wrote {out} (N={len(spam)+len(ham)})")
PY

log "make KIE natural test (N=$KIE_N) -> data/kie/test.jsonl"
python - <<'PY'
import json, random, pathlib
random.seed(20240904)
KIE_N = int(__import__("os").environ.get("KIE_N","50"))
def one(i):
    cur = random.choice(["USD","RMB","TWD","EUR"])
    amt = random.choice(["12,800","5,000","68,000","2,450"])
    env = random.choice(["正式環境","沙箱環境","預備環境","staging"])
    sla = random.choice(["24 小時內","48 小時內","3 個工作天內","今晚 20:00 前"])
    date= random.choice(["2025/10/01","2025-11-20","2025-12-31","2026/01/15"])
    text = f"請儘速核撥款項 {cur} {amt}，並部署到{env}。時限為 {sla}，截止日：{date}。"
    # span 對齊字元偏移
    a_s = text.index(cur); a_e = a_s + (len(cur)+1+len(amt))
    e_s = text.index(env); e_e = e_s + len(env)
    s_s = text.index(sla); s_e = s_s + len(sla)
    d_s = text.rindex(date); d_e = d_s + len(date)
    spans=[{"label":"amount","start":a_s-0,"end":a_e},
           {"label":"env","start":e_s,"end":e_e},
           {"label":"sla","start":s_s,"end":s_e},
           {"label":"date_time","start":d_s,"end":d_e}]
    return {"id": f"ex-{i:04d}", "text": text, "spans": spans}

rows = [one(i+1) for i in range(KIE_N)]
out = pathlib.Path("data/kie/test.jsonl")
out.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows), encoding="utf-8")
print(f"[OK] wrote {out} (N={len(rows)})")
PY

log "eval SPAM (Ensemble/Text/Rule) -> reports_auto/spam_cn_eval.txt"
PYTHONPATH=src python scripts/sma_quick_eval.py --data data/cn_spam_eval.jsonl --out reports_auto/spam_cn_eval.txt || true

# KIE 如需評測，需 transformers/torch + 權重就緒；條件符合才跑
if [[ -f ".sma_tools/kie_eval_strict.py" && -e "artifacts/releases/kie_xlmr/current" ]]; then
  python .sma_tools/kie_eval_strict.py \
    --model_dir artifacts/releases/kie_xlmr/current \
    --test data/kie/test.jsonl \
    --out_prefix reports_auto/kie_eval || true
else
  echo "[skip] KIE eval（缺 .sma_tools/kie_eval_strict.py 或 KIE 權重）"
fi

echo "[preview]"
sed -n '1,3p' data/cn_spam_eval.jsonl | sed -n '1,2p'
sed -n '1,2p' data/kie/test.jsonl || true
echo "[reports] 在 ./reports_auto/"
