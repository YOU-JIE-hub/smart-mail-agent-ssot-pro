# Intent 標註說明（JSONL）
每行一筆：
{"text": "<郵件或句子>", "label": "<biz_quote|tech_support|policy_qa|profile_update|complaint|other>"}

建議拆 train/val/test 三份，先從 100~500 筆起步，逐步擴充。
標註一致性很關鍵：可寫 10~20 條「判斷規則」給標註者參考。
