"""The running service: config, database, job queue, Plex. The API routes, the
CLI and the MCP server all go through one Core."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import requests

from . import config as cfgmod
from .auth import Keys
from .clients.plex import PlexClient
from .config import Config
from .db import Database
from .jobs import JobStore, Worker
from .stages import vocab
from .states import Caps, caps
from .store import Store

log = logging.getLogger("marcarr")


class Core:
    def __init__(self, cfg: Config, cfg_path: Path | str | None = None, *, start_worker: bool = True):
        self.cfg = cfg
        self.cfg_path = Path(cfg_path) if cfg_path else cfgmod.default_path()
        self.cfg.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(cfg.db_path)
        self.store = Store(self.db)
        vocab.use_custom(self.store.custom_tags)  # tag lookups see "My tags" too
        self.jobs = JobStore(self.db)
        self.keys = Keys(self.db)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Marcarr"
        self._lock = threading.Lock()
        self._plex: PlexClient | None = None
        self._plex_key: tuple[str, str] | None = None
        self._caps: Caps | None = None

        from . import cuts, events, library, pipeline, research

        self.events = events.Events(self)
        self.pipeline = pipeline.Pipeline(self)
        self.library = library.Library(self)
        self.cuts = cuts.Cuts(self)
        self.research = research.Research(self)
        handlers = {
            "analyse": self.pipeline.job_analyse,
            "scan": self.library.job_scan,
            "labels": self.library.job_labels,
            "face_models": self.pipeline.job_face_models,
            "compare": self.cuts.job_compare,
            "research": self.research.job_research,
        }
        self.worker = Worker(self.jobs, handlers, on_finish=self._finished,
                             heavy_threads=int(cfg.analysis.at_once))
        self._move_ai_key()
        if self.store.kv("paused", False):
            self.worker.pause()
        if start_worker:
            self.worker.start()

    # -- config ------------------------------------------------------------------------
    def _move_ai_key(self) -> None:
        """The single AI key of the first settings goes under its model's provider."""
        ai_cfg = self.cfg.ai
        prov = ai_cfg.model.split("/", 1)[0] if "/" in ai_cfg.model else ""
        if ai_cfg.api_key and prov and prov not in (ai_cfg.keys or {}):
            new = self.cfg.model_copy(deep=True)
            new.ai.keys = {**(ai_cfg.keys or {}), prov: ai_cfg.api_key}
            new.ai.api_key = ""
            try:
                self.save_config(new)
            except Exception:  # noqa: BLE001 - a read-only config keeps working as before
                log.warning("could not move the AI key under %s", prov)

    def save_config(self, new: Config) -> None:
        with self._lock:
            cfgmod.save(new, self.cfg_path)
            self.cfg = new
            self._caps = None
            self._plex = None

    def caps(self) -> Caps:
        if self._caps is None:
            self._caps = caps(self.cfg)
        return self._caps

    def forget_caps(self) -> None:
        self._caps = None

    @property
    def data_dir(self) -> Path:
        return self.cfg.data_dir

    # -- Plex --------------------------------------------------------------------------
    def plex(self) -> PlexClient | None:
        url, token = self.cfg.plex.url.strip(), self.cfg.plex.token.strip()
        if not url or not token:
            return None
        if self._plex is None or self._plex_key != (url, token):
            self._plex = PlexClient(url, token, timeout=self.cfg.plex.timeout)
            self._plex_key = (url, token)
        return self._plex

    def plex_state(self) -> str:
        """connected | not set | failing (cached for a minute)."""
        import time

        plex = self.plex()
        if plex is None:
            return "not set"
        cached = getattr(self, "_plex_state", None)
        if cached and time.time() - cached[1] < 60 and cached[2] == self._plex_key:
            return cached[0]
        try:
            plex.identity()
            state = "connected"
        except Exception:  # noqa: BLE001 - any failure is "failing"
            state = "failing"
        self._plex_state = (state, time.time(), self._plex_key)
        return state

    def map_path(self, path: str) -> str:
        """Plex's path for a file -> the path Marcarr opens."""
        for m in self.cfg.plex.path_map:
            src = m.from_.rstrip("/\\")
            if src and (path == src or path.startswith(src + "/") or path.startswith(src + "\\")):
                return m.to.rstrip("/\\") + path[len(src):]
        return path

    # -- jobs --------------------------------------------------------------------------
    def _finished(self, job: dict[str, Any]) -> None:
        if job["kind"] == "analyse":
            self.pipeline.finished(job)

    def close(self) -> None:
        self.worker.stop()
        if vocab._custom_source == self.store.custom_tags:
            vocab.use_custom(None)
        self.db.close()
