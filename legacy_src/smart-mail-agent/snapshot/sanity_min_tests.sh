#!/usr/bin/env bash
set -Eeuo pipefail
echo "== sanity: run_action_handler (stdin + flags) =="
echo '{"subject":"FAQ","predicted_label":"reply_faq","attachments":[{"filename":"invoice.pdf.exe","size":1}]}' \
| python -m src.run_action_handler --out data/output/sanity.json --dry-run --simulate-failure
cat data/output/sanity.json
echo
echo "== sanity: spamcheck =="
python -m src.smart_mail_agent.cli_spamcheck --subject "FREE bonus" --content "see tinyurl.com/x" --sender "s@x.com" --explain
echo
echo "== sanity: send_with_attachment shim =="
python send_with_attachment_shim.py --to a@b.c --subject S --body B --file /tmp/x.pdf
echo
