from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from typing import Any, Dict, List, Optional

class Executor:
    def __init__(self, workdir: Path, outbox: Path, db_path: Path, dry_run: bool = False) -> None:
        self.workdir = Path(workdir)
        self.outbox = Path(outbox)
        self.db_path = Path(db_path)
        self.dry_run = dry_run
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)

    # ---------------- DB helpers ----------------
    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS exec_log(ts REAL, step_id TEXT, action TEXT, ok INT, detail TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS tickets(ts REAL, ticket_id TEXT, queue TEXT, title TEXT, status TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS events(ts REAL, title TEXT, duration INT)")
        cur.execute("CREATE TABLE IF NOT EXISTS audits(ts REAL, step_id TEXT, action TEXT, detail TEXT)")
        conn.commit()

    def _db(self) -> Optional[sqlite3.Connection]:
        try:
            conn = sqlite3.connect(self.db_path)
            self._ensure_schema(conn)
            return conn
        except Exception:
            return None

    def _db_exec(self, sql: str, params: tuple) -> None:
        conn = self._db()
        if not conn:
            return
        try:
            conn.execute(sql, params)
            conn.commit()
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _log(self, step_id: str, action: str, ok: bool, detail: Dict[str, Any]) -> None:
        self._db_exec(
            "INSERT INTO exec_log VALUES (?,?,?,?,?)",
            (time.time(), step_id, action, 1 if ok else 0, json.dumps(detail, ensure_ascii=False)),
        )

    def _insert_ticket(self, queue: str, title: str) -> str:
        tid = f"T{int(time.time()*1000)}"
        self._db_exec(
            "INSERT INTO tickets VALUES (?,?,?,?,?)",
            (time.time(), tid, queue, title, "open"),
        )
        return tid

    def _insert_event(self, title: str, duration: int) -> None:
        self._db_exec(
            "INSERT INTO events VALUES (?,?,?)",
            (time.time(), title, int(duration)),
        )

    def _insert_audit(self, step_id: str, action: str, detail: Dict[str, Any]) -> None:
        self._db_exec(
            "INSERT INTO audits VALUES (?,?,?,?)",
            (time.time(), step_id, action, json.dumps(detail, ensure_ascii=False)),
        )

    # --------------- file helpers ---------------
    def _write_file(self, path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _doc_output_name(self, step_id: str, params: Dict[str, Any]) -> str:
        fmt = params.get("format", "pdf")
        # 企業規劃：quote 模板固定出 quote.pdf
        if params.get("template") == "quote":
            return f"quote.{fmt}"
        if params.get("output_name"):
            return str(params["output_name"])
        return f"{step_id}.{fmt}"

    # --------------- simulate / real ---------------
    def _simulate(self, step: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        sid = step.get("id"); action = step.get("action",""); params = step.get("params",{})
        if action == "email.reply":
            return {"dry_run": True, "would_write": str(self.outbox / f"{sid}.eml"),
                    "template": params.get("template","auto"), "attach": params.get("attach")}
        if action == "doc.render":
            outname = self._doc_output_name(sid or "doc", params)
            return {"dry_run": True, "would_write": str(self.workdir / outname),
                    "template": params.get("template",""), "format": params.get("format","pdf")}
        if action == "pricing.calc":
            qty = int(params.get("qty", ctx.get("qty", 1)))
            return {"dry_run": True, "total": qty*100, "currency":"USD"}
        if action == "calendar.book":
            return {"dry_run": True, "scheduled": True, "duration_min": params.get("duration_min",30)}
        if action == "crm.qualify":
            return {"dry_run": True, "qualified": True, "model": params.get("model","bant")}
        if action == "ticket.create":
            return {"dry_run": True, "queue": params.get("queue","support")}
        if action == "context.attach":
            hints = params.get("hints", [])
            return {"dry_run": True, "hints": hints, "count": len(hints)}
        return {"dry_run": True}

    def _exec_real(self, step: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        sid = step.get("id"); action = step.get("action",""); params = step.get("params",{})
        if action == "email.reply":
            filename = f"{int(time.time()*1000)}_{sid}.eml"
            p = self.outbox / filename
            body = params.get("template","auto")
            if "attach" in params:
                body += f"\nATTACH={params['attach']}"
            path = self._write_file(p, body)
            res = {"ok": True, "path": path}
            self._insert_audit(sid or "", action, res)
            return res

        if action == "doc.render":
            outname = self._doc_output_name(sid or "doc", params)
            p = self.workdir / outname
            content = f"TEMPLATE={params.get('template','')}\nCTX={json.dumps(ctx,ensure_ascii=False)}"
            path = self._write_file(p, content)
            res = {"ok": True, "path": path}
            self._insert_audit(sid or "", action, res)
            return res

        if action == "pricing.calc":
            qty = int(params.get("qty", ctx.get("qty", 1)))
            return {"ok": True, "total": qty*100, "currency":"USD"}

        if action == "calendar.book":
            dur = int(params.get("duration_min", 30))
            title = ctx.get("meeting_title") or "Meeting"
            self._insert_event(title, dur)
            return {"ok": True, "scheduled": True, "duration_min": dur, "title": title}

        if action == "crm.qualify":
            return {"ok": True, "qualified": True, "model": params.get("model","bant")}

        if action == "ticket.create":
            queue = params.get("queue","support")
            title = ctx.get("ticket_title") or "Support request"
            tid = self._insert_ticket(queue, title)
            return {"ok": True, "ticket_id": tid, "queue": queue}

        if action == "context.attach":
            hints = params.get("hints", [])
            res = {"ok": True, "hints": hints, "count": len(hints)}
            self._insert_audit(sid or "", action, res)
            return res

        return {"ok": True}

    def _exec_one(self, step: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        sid = step.get("id"); action = step.get("action","")
        try:
            if self.dry_run:
                res = self._simulate(step, ctx)
                out = {"id": sid, "action": action, "ok": True, "result": res}
            else:
                res = self._exec_real(step, ctx)
                out = {"id": sid, "action": action, "ok": bool(res.get("ok", True)), "result": res}
            self._log(sid or "", action, bool(out.get("ok", True)), out.get("result", {}))
            return out
        except Exception as e:
            err = {"error": str(e)}
            self._log(sid or "", action, False, err)
            return {"id": sid, "action": action, "ok": False, "result": err}

    def execute(self, steps: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [self._exec_one(s, context) for s in (steps or [])]
