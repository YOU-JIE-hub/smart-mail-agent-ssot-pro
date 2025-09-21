# CLI 指南
- spam 規則檢查：python -m smart_mail_agent.cli_spamcheck --subject "xxx" --body "yyy"
- 動作路由（離線展示）：OFFLINE=1 python -m smart_mail_agent.routing.run_action_handler --input data/sample/email.json
