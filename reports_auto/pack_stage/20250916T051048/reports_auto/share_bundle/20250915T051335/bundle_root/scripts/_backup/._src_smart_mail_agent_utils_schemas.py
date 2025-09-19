# Mail: {id, subject, sender, body, ts}
# Intent6: {"quote","order","invoice","logistics","warranty","general"}
# Action: {id, status, spam, intent{intent,score,needs_review,top2}, kie{fields,coverage}, alerts[], tickets[], artifacts[], outbox[], ts, latency_ms}
# KIE fields (baseline): amount, order_id, invoice_title, vat, tracking_no, po_no, rma_no
