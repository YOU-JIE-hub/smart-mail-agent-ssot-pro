# Smart Mail Agent

一個可離線驗證的 AI + RPA 郵件處理範例專案。
快速連結：
- [Architecture](architecture.md)
- [Cookbook](cookbook.md)

**離線展示：**
```bash
scripts/demo_offline.sh
離線測試：

bash
Copy
Edit
pytest -q tests/unit tests/contracts -m "not online" \
  --cov=src/smart_mail_agent --cov-report=term-missing --cov-report=xml
