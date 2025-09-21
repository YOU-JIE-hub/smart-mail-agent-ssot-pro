#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"

log(){ printf '[%s] %s\n' "$(date +%F' '%T)" "$*"; }

SPAM_N="${SPAM_N:-100}"   # 產生 SPAM_N spam + SPAM_N ham（預設 100+100=200）
KIE_N="${KIE_N:-50}"      # 產生 KIE_N 筆（預設 50 筆自然語氣樣本）

mkdir -p data data/kie reports_auto

# -------------------------------------- #
# 1) 產生「中文 Spam 測試集」 -> data/cn_spam_eval.jsonl
# -------------------------------------- #
log "make Chinese spam eval (N_spam=$SPAM_N, N_ham=$SPAM_N) -> data/cn_spam_eval.jsonl"
python - <<'PY'
import json, random, pathlib
random.seed(20240904)
SPAM_N = int(__import__("os").environ.get("SPAM_N", "100"))
HAM_N  = SPAM_N

cats_spam = {
  "釣魚/驗證": [
    ("【安全提醒】您的帳戶異常登入", "我們偵測到風險登入，請於24小時內點擊{url}驗證身分，逾期將停用。"),
    ("重設密碼通知", "為維護安全，請使用以下連結重設密碼：{url}，若已處理請忽略。"),
    ("提醒：二步驟驗證未完成", "系統偵測到您的2FA未啟用，請前往 {url} 完成設定。")
  ],
  "促銷/廣告": [
    ("中秋檔期限時8折", "全館家電最低下殺，輸入折扣碼【MOON】再折200，活動詳情：{url}"),
    ("年底清倉，一件不留", "全站滿額贈，今日下單再送VIP禮券，點我搶購：{url}"),
    ("會員日 85 折", "限時 48 小時，指定品類再享加碼；活動辦法：{url}")
  ],
  "貸款/金融": [
    ("核貸通過 24H 撥款", "學生也能辦，年利率低至1.8%，加LINE：{url} 立即試算。"),
    ("信用卡升等成功", "尊榮黑卡候選人，回覆本信或前往：{url} 完成身分驗證。"),
    ("投資提醒", "立即開戶送手續費折抵，點此 {url} 把握機會。")
  ],
  "發票/海關/退款": [
    ("海關補稅通知", "包裹需補稅NT${amt}，請於48小時內至{url}繳費，否則退運。"),
    ("退款申請已受理", "請於系統填寫退款帳戶：{url}，以利3日內入帳。"),
    ("發票異常待補件", "請上傳資料至 {url} 完成審核，逾期將影響入帳。")
  ],
  "色情/賭博": [
    ("真人發牌註冊送1688", "新戶首存三倍送，立即進入：{url}"),
    ("同城交友，限時免費見面", "填寫資料 10 秒配對成功：{url}"),
    ("體育下注高賠率", "世界盃熱潮，快來 {url} 體驗高返水。")
  ]
}

ham_topics = [
  ("本週例會議程", "大家好，週四15:00於A會議室，議程含專案進度與年度預算，請準時出席。"),
  ("發票收據彙整", "附件為八月份報帳資料，請審閱後回覆，若需補件再告知，謝謝。"),
  ("客戶回饋整理", "彙整了三個關鍵需求與兩項風險，細節見附件PPT。"),
  ("系統維護通知", "本週日 02:00-04:00 進行例行維護，期間登入可能受影響，敬請見諒。"),
  ("面試邀約", "您好，想邀請您下週二上午進行60分鐘線上面試，時間方便嗎？"),
  ("請款進度", "上次請款單已送審，預估三個工作天完成撥款。"),
  ("需求單確認", "針對流程第二步驟的欄位名稱，我們做了調整，請協助確認。"),
  ("上線檢查清單", "請協助填寫DB備份、回滾方案與監控指標，謝謝。"),
]

urls = [
  "https://acc-safe-check.com/verify",
  "https://promo-best-deal.shop",
  "https://fast-loan.xyz/apply",
  "https://customs-tax.top/pay",
  "https://casino777.cam/join",
]
def mk_spam(i):
  cat = random.choice(list(cats_spam.keys()))
  subj, body_t = random.choice(cats_spam[cat])
  url = random.choice(urls)
  amt = random.choice([368, 520, 880, 1299, 1850, 2680, 3880, 5200])
  body = body_t.format(url=url, amt=amt)
  return {"id": f"spam-{i:04d}", "subject": subj, "body": body, "attachments": [], "label": "spam"}

def mk_ham(i):
  subj, body = random.choice(ham_topics)
  return {"id": f"ham-{i:04d}", "subject": subj, "body": body, "attachments": [], "label": "ham"}

rows = []
for i in range(SPAM_N): rows.append(mk_spam(i))
for i in range(HAM_N):  rows.append(mk_ham(i))
random.shuffle(rows)

out = pathlib.Path("data/cn_spam_eval.jsonl")
with out.open("w", encoding="utf-8") as w:
  for r in rows: w.write(json.dumps(r, ensure_ascii=False)+"\n")
print(f"[OK] wrote {out} (N={len(rows)})")
PY

# -------------------------------------- #
# 2) 產生「KIE 自然語氣測試集 50 筆」-> data/kie/test.jsonl
#    標籤：amount / date_time / env / sla
# -------------------------------------- #
log "make KIE natural test (N=$KIE_N) -> data/kie/test.jsonl"
python - <<'PY'
import json, random, pathlib, datetime as dt
random.seed(20240904)
N = int(__import__("os").environ.get("KIE_N","50"))

def amt_variants():
  base = random.choice([980, 1050, 1250, 3200, 3500, 5000, 8800, 12800, 19999])
  forms = [
    f"NT${base:,}",
    f"新台幣 {base:,} 元",
    f"RMB {base:,}",
    f"USD {base:,}",
    f"¥{base:,}",
    f"{base:,} 元",
  ]
  return random.choice(forms)

ENV_TERMS = [
  "正式環境","生產環境","測試環境","預備環境","UAT 環境","Demo 環境","staging 環境","沙箱環境"
]
SLA_TERMS = [
  "24 小時內","48 小時內","72 小時內","12 小時回覆","4 小時回應","8 小時內處理","2 個工作天內","3 個工作天內"
]
def date_variants():
  d = dt.date(2025, random.choice([9,10,11,12]), random.choice([1,5,8,12,15,20,25,28]))
  choices = [
    d.strftime("%Y-%m-%d"),
    d.strftime("%Y/%m/%d"),
    d.strftime("%Y.%m.%d"),
    f"{d.year}年{d.month:02d}月{d.day:02d}日",
  ]
  return random.choice(choices)

# 多樣自然語氣模板（以「片段拼接」方式記錄 span 偏移）
TEMPLATES = [
  # 片段列表：("文字", 標籤或None)
  lambda A,E,S,D: [
    ("請儘速核撥款項 ", None), (A,"amount"), ("，並部署到",None), (E,"env"), ("。",None),
    ("時限為 ",None), (S,"sla"), ("，截止日：",None), (D,"date_time"), ("。",None)
  ],
  lambda A,E,S,D: [
    ("報告：",None), ("本次費用為 ",None), (A,"amount"), ("；",None), ("請在 ",None), (E,"env"),
    (" 完成驗收。",None), ("SLA：",None), (S,"sla"), ("，預計上線日 ",None), (D,"date_time"), ("。",None)
  ],
  lambda A,E,S,D: [
    ("請開立發票金額",None), (A,"amount"), ("，先佈署於",None), (E,"env"),
    ("，服務等級協議為 ",None), (S,"sla"), ("，預計完成日 ",None), (D,"date_time"), ("。",None)
  ],
  lambda A,E,S,D: [
    ("本次維護費用為 ",None), (A,"amount"), ("，目標環境：",None), (E,"env"),
    ("，SLA 承諾 ",None), (S,"sla"), ("，最晚 ",None), (D,"date_time"), (" 前完成。",None)
  ],
  lambda A,E,S,D: [
    ("總款項 ",None), (A,"amount"), (" 已核，請於",None), (E,"env"), ("更新。",None),
    ("服務時限 ",None), (S,"sla"), ("，排程日 ",None), (D,"date_time"), ("。",None)
  ],
  lambda A,E,S,D: [
    ("請於 ",None), (D,"date_time"), (" 前完成小計 ",None), (A,"amount"),
    (" 的付款，並在 ",None), (E,"env"), (" 驗證，回覆時效 ",None), (S,"sla"), ("。",None)
  ],
  lambda A,E,S,D: [
    ("測試費 ",None), (A,"amount"), ("，請先上傳至 ",None), (E,"env"),
    ("，服務時限 ",None), (S,"sla"), ("，預估完成 ",None), (D,"date_time"), ("。",None)
  ],
  lambda A,E,S,D: [
    ("請核對 促銷折讓 ",None), (A,"amount"), (" ，先在 ",None), (E,"env"),
    (" 演示，SLA ",None), (S,"sla"), ("，預計 ",None), (D,"date_time"), (" 結案。",None)
  ],
  lambda A,E,S,D: [
    ("麻煩協助此案請款 ",None), (A,"amount"), ("，",None), ("驗收環境為 ",None), (E,"env"),
    ("。",None), ("目標回覆時間 ",None), (S,"sla"), ("；上線日 ",None), (D,"date_time"), ("。",None)
  ],
  lambda A,E,S,D: [
    ("此次異動金額 ",None), (A,"amount"), ("，請先於 ",None), (E,"env"),
    (" 驗證；",None), ("服務回應需達成 ",None), (S,"sla"), ("。最晚上線 ",None), (D,"date_time"), ("。",None)
  ],
]

def build_one(i):
  A = amt_variants()
  E = random.choice(ENV_TERMS)
  S = random.choice(SLA_TERMS)
  D = date_variants()
  tpl = random.choice(TEMPLATES)
  spans=[]; text=""; pos=0
  for seg,label in tpl(A,E,S,D):
    st=pos; text+=seg; pos+=len(seg)
    if label:
      spans.append({"label":label,"start":st,"end":pos})
  return {"id": f"ex-{i:04d}", "text": text, "spans": spans}

rows=[build_one(i) for i in range(1, N+1)]
out = pathlib.Path("data/kie/test.jsonl")
with out.open("w", encoding="utf-8") as w:
  for r in rows: w.write(json.dumps(r, ensure_ascii=False)+"\n")
print(f"[OK] wrote {out} (N={len(rows)})")
PY

# -------------------------------------- #
# 3)（可用則自動）評測 Spam / KIE
# -------------------------------------- #
ran_any=0

# Spam 評測（需要：scripts/sma_quick_eval.py + 模型 artifacts_prod/model_pipeline.pkl）
if [[ -f "scripts/sma_quick_eval.py" && -f "artifacts_prod/model_pipeline.pkl" ]]; then
  log "eval SPAM (Ensemble/Text/Rule) -> reports_auto/spam_cn_eval.txt"
  PYTHONPATH=src python scripts/sma_quick_eval.py --data data/cn_spam_eval.jsonl | tee reports_auto/spam_cn_eval.txt || true
  ran_any=1
else
  log "skip SPAM eval（缺 scripts/sma_quick_eval.py 或 artifacts_prod/model_pipeline.pkl）"
fi

# KIE 嚴格評測（需要：.sma_tools/kie_eval_strict.py + artifacts/releases/kie_xlmr/current）
if [[ -f ".sma_tools/kie_eval_strict.py" && -e "artifacts/releases/kie_xlmr/current" ]]; then
  # 檢查 transformers/torch 是否存在
  if python - <<'PY' >/dev/null 2>&1
import importlib; importlib.import_module("transformers"); importlib.import_module("torch")
PY
  then
    log "eval KIE strict-span -> reports_auto/kie_eval_cn.txt"
    python .sma_tools/kie_eval_strict.py \
      --model_dir artifacts/releases/kie_xlmr/current \
      --test data/kie/test.jsonl \
      --out_prefix reports_auto/kie_eval_cn || true
    ran_any=1
  else
    log "skip KIE eval（缺 transformers/torch）"
  fi
else
  log "skip KIE eval（缺 .sma_tools/kie_eval_strict.py 或 KIE 權重資料夾）"
fi

# 提示
log "preview heads:"
echo "  - data/cn_spam_eval.jsonl ->"; head -n 2 data/cn_spam_eval.jsonl || true
echo "  - data/kie/test.jsonl     ->"; head -n 2 data/kie/test.jsonl || true

if [[ "$ran_any" -eq 1 ]]; then
  log "reports in ./reports_auto/"
else
  log "未自動跑評測；資料已生成，可手動執行："
  echo "  PYTHONPATH=src python scripts/sma_quick_eval.py --data data/cn_spam_eval.jsonl"
  echo "  python .sma_tools/kie_eval_strict.py --model_dir artifacts/releases/kie_xlmr/current --test data/kie/test.jsonl --out_prefix reports_auto/kie_eval_cn"
fi

log "done."
