#!/usr/bin/env bash
# 產生一小包可測的 .eml 到 data/demo_eml
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
OUT="$ROOT/data/demo_eml"
mkdir -p "$OUT"

emit() {
  local fn="$1"; shift
  cat > "$OUT/$fn" <<'EOF'
From: demo@example.com
To: you@example.com
Subject: __SUBJ__
Date: Tue, 02 Sep 2025 10:00:00 +0800
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8

__BODY__
EOF
}

# 報價
emit "q_quote_01.eml"
sed -i 's/__SUBJ__/詢價：40 席授權與 SOW/g' "$OUT/q_quote_01.eml"
sed -i 's#__BODY__#您好，請提供 40 seats 年費與一次性費用試算（NT$ 200,000 區間），含 SLA 與 SOW 條款。下週二前需要報價與交期。#' "$OUT/q_quote_01.eml"

# 技術支援
emit "s_support_01.eml"
sed -i 's/__SUBJ__/系統錯誤：匯入 500/g' "$OUT/s_support_01.eml"
sed -i 's#__BODY__#上線後 API 匯入偶發 500/502，請協助排查（stacktrace 已附於連結），需要 on-call SLA。#' "$OUT/s_support_01.eml"

# 投訴
emit "c_complaint_01.eml"
sed -i 's/__SUBJ__/客訴：出貨延遲與缺件/g' "$OUT/c_complaint_01.eml"
sed -i 's#__BODY__#本週訂單多筆延遲且少寄，造成退款需求，請提供處理時程與賠償方案。#' "$OUT/c_complaint_01.eml"

# 規則詢問
emit "p_policy_01.eml"
sed -i 's/__SUBJ__/政策詢問：SLA 與終止條款/g' "$OUT/p_policy_01.eml"
sed -i 's#__BODY__#想確認 SLA 等級、RPO/RTO 與合約終止條款，是否提供違約金上限與流程 SOP？#' "$OUT/p_policy_01.eml"

# 資料異動
emit "u_profile_01.eml"
sed -i 's/__SUBJ__/個資異動：發票抬頭與聯絡電話/g' "$OUT/u_profile_01.eml"
sed -i 's#__BODY__#請協助更新公司名稱與統編，聯絡電話改為 02-1234-5678，並提供異動 diff 供審核。#' "$OUT/u_profile_01.eml"

# spam / phishing
emit "z_spam_01.eml"
sed -i 's/__SUBJ__/中獎通知，點此領取 100000 USDT/g' "$OUT/z_spam_01.eml"
sed -i 's#__BODY__#恭喜中獎！點擊 http://malicious.example.com 立即領取，否則帳號將停用。unsubscribe here.#' "$OUT/z_spam_01.eml"

echo "[OK] demo .eml ready -> $OUT"
