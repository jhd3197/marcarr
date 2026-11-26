"""API keys for connected apps, each with scopes:

* ``read``: everything GET
* ``propose``: add tags as proposals (FansCut, Doblarr, MCP clients)
* ``review``: keep, drop and edit tags, confirm faces (the review pages)
* ``run``: queue analysis

A request with a key is held to its scopes. A request without one is the web
UI or a trusted caller: allowed, unless ``server.require_key`` is on and the
call does not come from this machine. Settings and key management are never
open to a key: they are for the person at the web UI.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import secrets
import uuid
from typing import Any

from .db import Database, dumps
from .errors import MarcarrError, NotFoundError

SCOPES = ("read", "propose", "review", "run")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


class Keys:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        return {"id": r["id"], "name": r["name"], "prefix": r["prefix"],
                "scopes": json.loads(r["scopes"]), "created_at": r["created_at"],
                "last_used": r["last_used"]}

    def list(self) -> list[dict[str, Any]]:
        return [self._row(r) for r in self.db.query("SELECT * FROM api_keys ORDER BY created_at")]

    def add(self, name: str, scopes: list[str]) -> dict[str, Any]:
        name = (name or "").strip()[:60]
        if not name:
            raise MarcarrError("give the app a name")
        bad = [s for s in scopes if s not in SCOPES]
        if bad:
            raise MarcarrError(f"unknown scope: {', '.join(bad)}")
        key = "mk_" + secrets.token_urlsafe(24)
        kid = uuid.uuid4().hex[:10]
        self.db.execute("INSERT INTO api_keys (id, name, key_hash, prefix, scopes, created_at)"
                        " VALUES (?,?,?,?,?,?)",
                        (kid, name, _hash(key), key[:7], dumps(scopes or ["read"]), _now()))
        return {**self.get(kid), "key": key}

    def get(self, kid: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM api_keys WHERE id = ?", (kid,))
        if r is None:
            raise NotFoundError(f"key {kid} not found")
        return self._row(r)

    def renew(self, kid: str) -> dict[str, Any]:
        self.get(kid)
        key = "mk_" + secrets.token_urlsafe(24)
        self.db.execute("UPDATE api_keys SET key_hash = ?, prefix = ? WHERE id = ?",
                        (_hash(key), key[:7], kid))
        return {**self.get(kid), "key": key}

    def delete(self, kid: str) -> None:
        self.get(kid)
        self.db.execute("DELETE FROM api_keys WHERE id = ?", (kid,))

    def check(self, key: str) -> dict[str, Any] | None:
        r = self.db.one("SELECT * FROM api_keys WHERE key_hash = ?", (_hash(key),))
        if r is None:
            return None
        self.db.execute("UPDATE api_keys SET last_used = ? WHERE id = ?", (_now(), r["id"]))
        return self._row(r)
