"""SQLite store: one shared connection behind a lock, WAL, a tiny migration runner.

Statements autocommit; wrap several in transaction() to make them one unit.
The schema lives in schema.py."""

from __future__ import annotations

import contextlib
import datetime as _dt
import json
import sqlite3
import threading
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from .schema import MIGRATIONS


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._depth = 0  # nesting of transaction() on the thread holding the lock
        # isolation_level=None: no implicit transactions; transaction() opens them
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, far fewer fsyncs
        self._conn.execute("PRAGMA busy_timeout=5000")  # another process (the CLI) may write
        self._migrate()
        self._conn.execute("PRAGMA foreign_keys=ON")

    def _migrate(self) -> None:
        """Run pending migrations, each in one transaction with its user_version
        bump: a step that fails leaves the database as it was, not half-built."""
        with self._lock:
            have = self._conn.execute("PRAGMA user_version").fetchone()[0]
            for i, step in enumerate(MIGRATIONS[have:], start=have + 1):
                try:
                    self._conn.executescript(
                        f"BEGIN;\n{step()}\nPRAGMA user_version = {i};\nCOMMIT;")
                except sqlite3.Error:
                    if self._conn.in_transaction:
                        self._conn.execute("ROLLBACK")
                    raise

    @contextlib.contextmanager
    def transaction(self) -> Iterator[None]:
        """Group writes: all of them land, or none (nested calls join the outer one)."""
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield
            except BaseException:
                self._depth -= 1
                if outer:
                    self._conn.execute("ROLLBACK")
                raise
            self._depth -= 1
            if outer:
                self._conn.execute("COMMIT")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            self._conn.execute(sql, tuple(params))

    def prune(self, jobs_days: int = 30, http_days: int = 60) -> dict[str, int]:
        """Drop finished jobs and catalogue replies past their use, then let SQLite
        refresh its query statistics."""
        jobs_cut = (_dt.datetime.now() - _dt.timedelta(days=jobs_days)).isoformat(
            timespec="seconds")
        with self._lock:
            jobs = self._conn.execute(
                "DELETE FROM jobs WHERE status IN ('done','failed','cancelled')"
                " AND updated_at < ?", (jobs_cut,)).rowcount
            self._conn.execute("DELETE FROM webhook_calls WHERE at < ?", (jobs_cut,))
            http = self._conn.execute("DELETE FROM http_cache WHERE fetched_at < ?",
                                      (time.time() - http_days * 86400,)).rowcount
            self._conn.execute("PRAGMA optimize")
        return {"jobs": jobs, "http_cache": http}

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"))
