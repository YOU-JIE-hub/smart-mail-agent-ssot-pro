# -*- coding: utf-8 -*-
def pick_text(rec: dict) -> str:
  t = rec.get("text")
  if t and t.strip(): return t
  return (rec.get("subject","") + "\n" + rec.get("body","")).strip()
