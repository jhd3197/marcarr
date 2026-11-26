"""Reading the Plex libraries into titles and videos, and writing labels back.

A scan lists the movies and shows of the libraries picked in Settings,
upserts a title per film, show and episode (ids from identity.title_id), and
gives every file Marcarr can open a video (its content identity). A file
already seen at the same path, size and time is not read again.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import identity
from .errors import MarcarrError

if TYPE_CHECKING:
    from .core import Core
    from .jobs import JobContext

log = logging.getLogger("marcarr.library")
ARTICLES = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
PLEX_TYPE = {"movie": 1, "show": 2, "episode": 4}


def sort_name(name: str) -> str:
    return ARTICLES.sub("", name or "").lower()


def first_file(item: dict[str, Any]) -> tuple[str, str]:
    """(file path, edition) of a Plex item's first media part."""
    for media in item.get("Media") or []:
        for part in media.get("Part") or []:
            if part.get("file"):
                return str(part["file"]), str(item.get("editionTitle") or "")
    return "", ""


class Library:
    def __init__(self, core: Core):
        self.core = core
        self.store = core.store

    def submit_scan(self) -> dict[str, Any]:
        return self.core.worker.submit("scan", "Read the Plex libraries", {})

    def sections(self) -> list[dict[str, Any]]:
        plex = self.core.plex()
        if plex is None:
            raise MarcarrError("Plex is not set up yet")
        out = []
        for s in plex.sections():
            if s["type"] not in ("movie", "show"):
                continue
            try:
                count = plex.section_count(s["key"])
            except MarcarrError:
                count = None
            out.append({**s, "count": count})
        return out

    # -- scan --------------------------------------------------------------------------
    def job_scan(self, payload: dict[str, Any], ctx: JobContext) -> dict[str, Any]:
        plex = self.core.plex()
        if plex is None:
            raise MarcarrError("Plex is not set up yet")
        ident = plex.identity()
        if ident.get("machineIdentifier"):
            self.store.set_kv("plex_machine", ident["machineIdentifier"])
        wanted = set(self.core.cfg.plex.libraries)
        sections = [s for s in plex.sections() if s["type"] in ("movie", "show")
                    and (not wanted or s["key"] in wanted)]
        seen: set[str] = set()
        new_videos: list[str] = []
        stats = {"movies": 0, "shows": 0, "episodes": 0, "videos": 0, "unreadable": 0}
        for si, sec in enumerate(sections):
            ctx.check()
            if sec["type"] == "movie":
                items = plex.movies(sec["key"])
                for k, m in enumerate(items):
                    ctx.check()
                    ctx.progress((si + k / max(1, len(items))) / len(sections),
                                 f"{sec['title']}: {m.get('title', '')}")
                    tid = self._movie(m, sec["key"])
                    seen.add(tid)
                    stats["movies"] += 1
                    self._file(tid, m, stats, new_videos)
            else:
                shows = plex.shows(sec["key"])
                for k, sh in enumerate(shows):
                    ctx.check()
                    ctx.progress((si + k / max(1, len(shows))) / len(sections),
                                 f"{sec['title']}: {sh.get('title', '')}")
                    sid = self._show(sh, sec["key"])
                    seen.add(sid)
                    stats["shows"] += 1
                    try:
                        eps = plex.episodes(str(sh["ratingKey"]))
                    except MarcarrError as exc:
                        log.warning("episodes of %s: %s", sh.get("title"), exc)
                        continue
                    for e in eps:
                        eid = self._episode(e, sh, sid, sec["key"])
                        seen.add(eid)
                        stats["episodes"] += 1
                        self._file(eid, e, stats, new_videos)
        stats["gone"] = self.store.mark_gone(seen, [s["key"] for s in sections])
        if self.core.cfg.analysis.on_new and payload.get("analyse_new", True):
            for vid in new_videos:
                self.core.pipeline.submit(vid, only_needed=True)
        stats["new"] = len(new_videos)
        stats["message"] = (f"{stats['movies']} films, {stats['shows']} shows, "
                            f"{stats['episodes']} episodes; {len(new_videos)} new videos")
        return stats

    def _base(self, item: dict[str, Any], tid: str, ids: dict[str, Any], section: str) -> dict[str, Any]:
        dur = item.get("duration")
        return {
            "id": tid, "name": item.get("title") or "", "sort_name": sort_name(item.get("titleSort") or item.get("title") or ""),
            "year": item.get("year"), "plex_key": str(item.get("ratingKey") or "") or None,
            "plex_section": section, "summary": item.get("summary") or "",
            "poster": item.get("thumb") or "", "duration": round(dur / 1000, 3) if dur else None,
            **ids,
        }

    def _movie(self, m: dict[str, Any], section: str) -> str:
        tid, ids = identity.title_id(m)
        cols = [c.get("tag") for c in m.get("Collection") or [] if c.get("tag")]
        path, _ = first_file(m)
        self.store.upsert_title({**self._base(m, tid, ids, section), "type": "movie",
                                 "collection": cols[0] if cols else None,
                                 "file": self.core.map_path(path) if path else ""})
        return tid

    def _show(self, sh: dict[str, Any], section: str) -> str:
        tid, ids = identity.title_id(sh)
        self.store.upsert_title({**self._base(sh, tid, ids, section), "type": "show"})
        return tid

    def _episode(self, e: dict[str, Any], sh: dict[str, Any], sid: str, section: str) -> str:
        tid, ids = identity.title_id(e, sh)
        path, _ = first_file(e)
        row = {**self._base(e, tid, ids, section), "type": "episode", "parent_id": sid,
               "season": e.get("parentIndex"), "episode": e.get("index"),
               "file": self.core.map_path(path) if path else ""}
        row["sort_name"] = f"{sort_name(sh.get('title') or '')} {int(e.get('parentIndex') or 0):03d} {int(e.get('index') or 0):04d}"
        if not row["poster"]:
            row["poster"] = e.get("grandparentThumb") or ""
        self.store.upsert_title(row)
        return tid

    def _file(self, tid: str, item: dict[str, Any], stats: dict[str, int], new: list[str]) -> None:
        plex_path, edition = first_file(item)
        if not plex_path:
            return
        path = self.core.map_path(plex_path)
        p = Path(path)
        try:
            st = p.stat()
        except OSError:
            stats["unreadable"] += 1
            return
        known = self.store.video_at(path, st.st_size, st.st_mtime)
        if known is not None:
            self.store.touch_video(known["id"], tid)
            stats["videos"] += 1
            return
        try:
            ident = identity.content_identity(p, self.core.cfg.ffmpeg.probe_binary)
        except OSError:
            stats["unreadable"] += 1
            return
        before = self.store.db.one("SELECT id FROM videos WHERE content_key = ?", (ident["content_key"],))
        vid = self.store.upsert_video(tid, path, ident, identity.edition_of(path, edition))
        stats["videos"] += 1
        if before is None:
            new.append(vid)

    def add_file(self, tid: str, path: str) -> str:
        """Register a file for a title by hand (tests, the CLI)."""
        ident = identity.content_identity(path, self.core.cfg.ffmpeg.probe_binary)
        return self.store.upsert_video(tid, path, ident, identity.edition_of(path))

    # -- Plex labels -------------------------------------------------------------------
    def job_labels(self, payload: dict[str, Any], ctx: JobContext) -> dict[str, Any]:
        """Write marcarr:<tag> labels for the chosen tags to the titles that have
        them kept, and take ours off titles that no longer do."""
        plex = self.core.plex()
        if plex is None:
            raise MarcarrError("Plex is not set up yet")
        cfg = self.core.cfg.labels
        prefix = cfg.prefix
        wanted = set(cfg.tags)
        by_title: dict[str, set[str]] = {}
        for r in self.store.tags(status="accepted", tag=sorted(wanted) or None):
            t = self.store.title_or_none(r["title_id"])
            if t is None:
                continue
            target = t["parent_id"] if t["type"] == "episode" and t["parent_id"] else t["id"]
            by_title.setdefault(target, set()).add(r["tag"])
        written = 0
        titles = self.store.titles("type IN ('movie', 'show') AND plex_key IS NOT NULL")
        for i, t in enumerate(titles):
            ctx.check()
            ctx.progress(i / max(1, len(titles)), t["name"])
            mine = {prefix + x for x in by_title.get(t["id"], set())}
            try:
                meta = self.core.plex().metadata(str(t["plex_key"])) if self.core.plex() else {}
            except MarcarrError:
                continue
            have = {str(lb.get("tag")) for lb in meta.get("Label") or []}
            ours = {x for x in have if x.lower().startswith(prefix.lower())}
            add = sorted(mine - have)
            remove = sorted(ours - {m.lower() for m in mine} - mine)
            if not add and not remove:
                continue
            plex.set_labels(str(t["plex_key"]), PLEX_TYPE[t["type"]], add, remove)
            written += 1
            if add:
                self.core.events.emit("labels.written", {"title": t["id"], "labels": sorted(mine)})
        return {"titles": written, "message": f"Labels written on {written} titles"}
