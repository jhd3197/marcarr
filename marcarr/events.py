"""Events and webhooks: other apps hear when a step finishes or a tag is kept,
instead of polling.

Each webhook names the events it wants. A call is a JSON POST signed with the
webhook's secret (``X-Marcarr-Signature: sha256=<hmac of the body>``), sent
from a small thread pool so a slow app never holds up analysis. The last
calls are kept for the API page ("Last calls", "Send again").
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import requests

from .db import dumps
from .errors import MarcarrError, NotFoundError

if TYPE_CHECKING:
    from .core import Core

log = logging.getLogger("marcarr.events")

EVENTS: dict[str, str] = {
    "step.finished": "A step finished on a video",
    "video.analysed": "All seven steps are done",
    "tag.proposed": "A tag is waiting for review",
    "tag.kept": "A person kept a tag",
    "tag.dropped": "A person dropped a tag",
    "labels.written": "Labels were written to Plex",
}
KEEP_CALLS = 200


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


class Events:
    def __init__(self, core: Core):
        self.core = core
        self.db = core.db
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="marcarr-hook")

    # -- webhooks ----------------------------------------------------------------------
    def _hook(self, r: Any) -> dict[str, Any]:
        d = dict(r)
        d["events"] = json.loads(d["events"])
        d["enabled"] = bool(d["enabled"])
        last = self.db.one("SELECT code FROM webhook_calls WHERE webhook_id = ? ORDER BY at DESC"
                           " LIMIT 1", (d["id"],))
        d["state"] = "unused" if last is None else (
            "working" if last["code"] and 200 <= last["code"] < 300 else "failing")
        return d

    def hooks(self) -> list[dict[str, Any]]:
        return [self._hook(r) for r in self.db.query("SELECT * FROM webhooks ORDER BY created_at")]

    def hook(self, hid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM webhooks WHERE id = ?", (hid,))
        if r is None:
            raise NotFoundError(f"webhook {hid} not found")
        return self._hook(r)

    def public(self, h: dict[str, Any]) -> dict[str, Any]:
        return {k: h[k] for k in ("id", "url", "events", "enabled", "state")}

    def add_hook(self, url: str, events: list[str]) -> dict[str, Any]:
        url = (url or "").strip()
        if not url.startswith(("http://", "https://")):
            raise MarcarrError("a webhook URL starts with http:// or https://")
        bad = [e for e in events if e not in EVENTS]
        if bad:
            raise MarcarrError(f"unknown event: {', '.join(bad)}")
        hid = uuid.uuid4().hex[:10]
        self.db.execute("INSERT INTO webhooks (id, url, events, secret, enabled, created_at)"
                        " VALUES (?,?,?,?,1,?)",
                        (hid, url, dumps(events or list(EVENTS)), secrets.token_hex(16), _now()))
        return self.hook(hid)

    def edit_hook(self, hid: str, url: str | None = None, events: list[str] | None = None,
                  enabled: bool | None = None) -> dict[str, Any]:
        self.hook(hid)
        if url is not None:
            if not url.startswith(("http://", "https://")):
                raise MarcarrError("a webhook URL starts with http:// or https://")
            self.db.execute("UPDATE webhooks SET url = ? WHERE id = ?", (url, hid))
        if events is not None:
            bad = [e for e in events if e not in EVENTS]
            if bad:
                raise MarcarrError(f"unknown event: {', '.join(bad)}")
            self.db.execute("UPDATE webhooks SET events = ? WHERE id = ?", (dumps(events), hid))
        if enabled is not None:
            self.db.execute("UPDATE webhooks SET enabled = ? WHERE id = ?", (int(enabled), hid))
        return self.hook(hid)

    def delete_hook(self, hid: str) -> None:
        self.hook(hid)
        self.db.execute("DELETE FROM webhooks WHERE id = ?", (hid,))

    # -- sending -----------------------------------------------------------------------
    def emit(self, event: str, data: dict[str, Any]) -> None:
        """Send *event* to every enabled webhook that wants it (in the background)."""
        body = {"event": event, "at": _now(), **data}
        for h in self.hooks():
            if h["enabled"] and event in h["events"]:
                self.pool.submit(self._send, h, event, body)

    def _send(self, h: dict[str, Any], event: str, body: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(body, separators=(",", ":")).encode()
        sig = hmac.new(h["secret"].encode(), raw, hashlib.sha256).hexdigest()
        code, error = None, ""
        try:
            r = requests.post(h["url"], data=raw, timeout=10, headers={
                "Content-Type": "application/json", "User-Agent": "Marcarr",
                "X-Marcarr-Event": event, "X-Marcarr-Signature": f"sha256={sig}"})
            code = r.status_code
            if code >= 300:
                error = (r.text or "")[:200]
        except requests.RequestException as exc:
            error = exc.__class__.__name__
        cid = uuid.uuid4().hex[:10]
        self.db.execute("INSERT INTO webhook_calls (id, webhook_id, url, event, payload, at, code, error)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (cid, h["id"], h["url"], event, raw.decode(), _now(), code, error))
        self.db.execute("DELETE FROM webhook_calls WHERE id NOT IN (SELECT id FROM webhook_calls"
                        " ORDER BY at DESC LIMIT ?)", (KEEP_CALLS,))
        if error:
            log.info("webhook %s %s: %s %s", h["url"], event, code, error)
        return self.call(cid)

    def test(self, hid: str) -> dict[str, Any]:
        h = self.hook(hid)
        event = h["events"][0] if h["events"] else "step.finished"
        return self._send(h, event, {"event": event, "at": _now(), "test": True})

    def calls(self, limit: int = 50) -> list[dict[str, Any]]:
        return [self._call(r) for r in self.db.query(
            "SELECT * FROM webhook_calls ORDER BY at DESC LIMIT ?", (limit,))]

    @staticmethod
    def _call(r: Any) -> dict[str, Any]:
        return {"id": r["id"], "webhook": r["webhook_id"], "url": r["url"], "event": r["event"],
                "at": r["at"], "code": r["code"], "error": r["error"]}

    def call(self, cid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM webhook_calls WHERE id = ?", (cid,))
        if r is None:
            raise NotFoundError(f"call {cid} not found")
        return self._call(r)

    def resend(self, cid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM webhook_calls WHERE id = ?", (cid,))
        if r is None:
            raise NotFoundError(f"call {cid} not found")
        h = self.hook(r["webhook_id"])
        return self._send(h, r["event"], json.loads(r["payload"]))
