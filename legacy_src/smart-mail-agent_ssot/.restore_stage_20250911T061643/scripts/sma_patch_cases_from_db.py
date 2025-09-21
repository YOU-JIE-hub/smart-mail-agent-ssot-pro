#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從 db/sma.sqlite 回填最新 E2E run 的 cases.jsonl：
- 自動偵測 intent_preds 與 kie_spans 欄位命名差異（label/pred_label/prob/intent_conf 等）
- 優先用 DB 寫出 cases；沒有就寫出合成佔位
- 所有錯誤寫入 reports_auto/errors/PATCH_CASES_<ts>/error.log
"""
from pathlib import Path
import sys, json, time, sqlite3, re, traceback, random

ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot").resolve()
TS = time.strftime("%Y%m%dT%H%M%S")
ERRDIR = ROOT / f"reports_auto/errors/PATCH_CASES_{TS}"
ERRDIR.mkdir(parents=True, exist_ok=True)

def elog(msg, exc=False):
    with (ERRDIR/"error.log").open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%F %T')}] {msg}\n")
        if exc:
            f.write(traceback.format_exc()+"\n")

def pick_run(run_arg: str|None):
    if run_arg:
        p = Path(run_arg); 
        return p if p.is_absolute() else (ROOT/p)
    base = ROOT/"reports_auto/e2e_mail"
    if not base.exists(): return None
    xs = [p for p in base.iterdir() if p.is_dir() and re.match(r"^\d{8}T\d{6}$", p.name)]
    xs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return xs[0] if xs else None

def table_cols(cur, t):
    cur.execute(f"PRAGMA table_info({t})")
    return [r[1] for r in cur.fetchall()]

def discover_intent_row(cur, case_id):
    # 嘗試不同欄位命名
    cols = table_cols(cur, "intent_preds")
    intent, conf = None, None
    # 候選查詢（依信心排序取一筆）
    candidates = []
    if {"case_id","label","prob"} <= set(cols):
        candidates.append(("SELECT label,prob FROM intent_preds WHERE case_id=? ORDER BY prob DESC LIMIT 1",))
    if {"case_id","pred_label","pred_conf"} <= set(cols):
        candidates.append(("SELECT pred_label,pred_conf FROM intent_preds WHERE case_id=? ORDER BY pred_conf DESC LIMIT 1",))
    if {"case_id","intent","score"} <= set(cols):
        candidates.append(("SELECT intent,score FROM intent_preds WHERE case_id=? ORDER BY score DESC LIMIT 1",))
    if not candidates:
        return (None, None)
    for (sql,) in candidates:
        cur.execute(sql, (case_id,))
        row = cur.fetchone()
        if row:
            intent, conf = row[0], float(row[1]) if row[1] is not None else None
            break
    return (intent, conf)

def read_kie_spans(cur, case_id):
    try:
        cols = table_cols(cur, "kie_spans")
    except Exception:
        return []
    need = {"case_id","key","value","start","end"}
    if not (need <= set(cols)):
        # 盡力取用可用欄位
        sel = [c for c in cols if c in ("key","value","start","end","label")]
        if not sel:
            return []
        cur.execute(f"SELECT {','.join(sel)} FROM kie_spans WHERE case_id=?", (case_id,))
        out=[]
        for r in cur.fetchall():
            d={}
            for k,v in zip(sel,r):
                if k=="label": k="key"
                d[k]=v
            out.append(d)
        return out
    cur.execute("SELECT key,value,start,end FROM kie_spans WHERE case_id=?", (case_id,))
    return [{"label":k, "value":v, "start":s, "end":e} for (k,v,s,e) in cur.fetchall()]

def discover_case_ids(cur, limit=50):
    # 依序嘗試常見表
    for t in ("intent_preds","kie_spans","actions"):
        try:
            cur.execute(f"SELECT DISTINCT case_id FROM {t} ORDER BY rowid DESC LIMIT {limit}")
            xs = [r[0] for r in cur.fetchall() if r and r[0]]
            if xs: return xs
        except Exception:
            continue
    return []

def synth_cases(n=10):
    intents=["報價","技術支援","投訴","規則詢問","資料異動","其他"]
    out=[]
    for i in range(n):
        cid=f"synthetic_{TS}_{i:03d}"
        it=random.choice(intents)
        out.append({
            "id": cid,
            "case_id": cid,
            "intent": it,
            "fields": {"spans":[{"label":"amount","value":"NT$ 10,000","start":0,"end":0}]},
            "text": f"意圖:{it}；欄位:amount=NT$10,000；關鍵詞:報價 試算 折扣 採購 合約 SOW"
        })
    return out

def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="")
    args = ap.parse_args(argv)

    run = pick_run(args.run_dir)
    if not run:
        print("[FATAL] no e2e run dir"); return 2
    cj = run/"cases.jsonl"

    db = ROOT/"db/sma.sqlite"
    rows_out=[]
    if db.exists():
        try:
            con = sqlite3.connect(db.as_posix())
            cur = con.cursor()
            case_ids = discover_case_ids(cur, 200)
            for cid in case_ids:
                it, cf = None, None
                try:
                    it, cf = discover_intent_row(cur, cid)
                except Exception:
                    elog(f"discover_intent_row failed: {cid}", exc=True)
                spans = []
                try:
                    spans = read_kie_spans(cur, cid)
                except Exception:
                    elog(f"read_kie_spans failed: {cid}", exc=True)
                rec = {
                    "id": cid,
                    "case_id": cid,
                    "intent": it or "其他",
                    "intent_conf": cf,
                    "fields": {"spans": spans}
                }
                rows_out.append(rec)
        except Exception:
            elog("sqlite error", exc=True)

    if not rows_out:
        rows_out = synth_cases(10)

    bak = cj.with_name(f"{cj.name}.bak_{TS}")
    if cj.exists():
        bak.write_text(cj.read_text(encoding="utf-8"), encoding="utf-8")
    with cj.open("w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False)+"\n")

    (run/"PATCH_CASES_SUMMARY.md").write_text(
        "# Patch Cases Summary\n"
        f"- run_dir: {run.as_posix()}\n"
        f"- from_db: {int(db.exists())}\n"
        f"- written: {len(rows_out)}\n"
        f"- backup: {bak.name if bak.exists() else '-'}\n", encoding="utf-8"
    )
    print(f"[OK] cases.jsonl patched -> {cj.as_posix()}  lines={len(rows_out)}")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        pass
    except Exception:
        elog("fatal", exc=True)
        print("[FATAL] patch failed")
