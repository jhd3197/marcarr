"""What a file is, independent of where it lives (Doblarr's identity model).

A **title** id comes from a provider when Plex knows one (``movie:tmdb:671``,
``show:tvdb:79168``, ``episode:tvdb:79168:s01e02``), else from the Plex rating
key (``plex:12345``): never from a folder name.

A **video** is one source revision of a title: a sampled hash of the file
(head, middle, tail) plus its size, duration and stream layout. The same file
at a new path is the same video; a re-encode or another cut is a new one.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

SAMPLE_BYTES = 1 << 20
METHOD = "sampled-sha256/1"
EDITION_WORDS = re.compile(
    r"\b(director'?s cut|extended(?: edition| cut)?|uncut|unrated|theatrical(?: cut)?|"
    r"remaster(?:ed)?|special edition|final cut|tv cut)\b",
    re.IGNORECASE)


def probe(path: str | Path, ffprobe: str = "ffprobe", timeout: float = 60) -> dict[str, Any]:
    """Duration, size of the picture and the stream layout from ffprobe ({} if unreadable)."""
    try:
        out = subprocess.run(  # noqa: S603 - argv list
            [ffprobe, "-v", "error", "-print_format", "json", "-show_entries",
             "format=duration:stream=index,codec_type,codec_name,channels,width,height,"
             "avg_frame_rate:stream_tags=language,title", str(path)],
            capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if out.returncode:
        return {}
    try:
        data = json.loads(out.stdout or b"{}")
    except ValueError:
        return {}
    streams = []
    width = height = None
    for row in data.get("streams") or []:
        tags = row.get("tags") or {}
        s = {k: v for k, v in {
            "index": row.get("index"), "type": row.get("codec_type"),
            "codec": row.get("codec_name"), "channels": row.get("channels"),
            "width": row.get("width"), "height": row.get("height"),
            "language": str(tags.get("language") or ""), "title": str(tags.get("title") or ""),
        }.items() if v not in (None, "")}
        streams.append(s)
        if s.get("type") == "video" and width is None and s.get("width"):
            width, height = s.get("width"), s.get("height")
    try:
        duration = float((data.get("format") or {}).get("duration") or "")
    except (TypeError, ValueError):
        duration = None
    return {"duration": duration, "width": width, "height": height, "streams": streams}


def content_identity(path: str | Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    """The identity of a file's content. Reads at most three MiB, so a two-hour
    film costs the same as a clip."""
    p = Path(path)
    stat = p.stat()
    digest = hashlib.sha256(str(stat.st_size).encode())
    with p.open("rb") as stream:
        offsets = sorted({0, max(0, stat.st_size // 2 - SAMPLE_BYTES // 2),
                          max(0, stat.st_size - SAMPLE_BYTES)})
        for offset in offsets:
            stream.seek(offset)
            digest.update(stream.read(SAMPLE_BYTES))
    info = probe(p, ffprobe)
    layout = [[s.get("index"), s.get("type"), s.get("codec"), s.get("channels"),
               s.get("language")] for s in info.get("streams") or []]
    digest.update(json.dumps([round(info.get("duration") or 0.0, 1), layout]).encode())
    return {"content_key": "c" + digest.hexdigest()[:24], "size": stat.st_size,
            "mtime": stat.st_mtime, "method": METHOD, **info}


def video_id(content_key: str) -> str:
    """The short id shown in URLs: 8 hex characters of the content key."""
    return content_key.lstrip("c")[:8]


EDITION_TAG = re.compile(r"\{edition-([^}]+)\}", re.IGNORECASE)


def edition_of(path: str, plex_edition: str = "") -> str:
    """The cut a file is: Plex's edition title, Plex's {edition-...} file name tag, or
    the words of the file name (Extended, Director's Cut...). Empty when none says."""
    if plex_edition:
        return plex_edition
    stem = Path(path).stem
    tag = EDITION_TAG.search(stem)
    if tag:
        return " ".join(tag.group(1).split())
    m = EDITION_WORDS.search(stem.replace(".", " ").replace("_", " "))
    return m.group(1).title().replace("Directors", "Director's").replace("Director'S", "Director's") if m else ""


def _guids(item: dict[str, Any]) -> dict[str, str]:
    """Plex's Guid list -> {"tmdb": "671", "tvdb": "79168", "imdb": "tt..."}."""
    out: dict[str, str] = {}
    for g in item.get("Guid") or []:
        gid = str(g.get("id") or "")
        if "://" in gid:
            kind, value = gid.split("://", 1)
            out.setdefault(kind, value)
    legacy = str(item.get("guid") or "")
    for kind, pat in (("tmdb", r"themoviedb://(\d+)"), ("tvdb", r"thetvdb://(\d+)"),
                      ("imdb", r"imdb://(tt\d+)")):
        m = re.search(pat, legacy)
        if m:
            out.setdefault(kind, m.group(1))
    return out


def title_id(item: dict[str, Any], show: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """(id, provider ids) for a Plex movie, show or episode item."""
    g = _guids(item)
    ids = {"tmdb_id": int(g["tmdb"]) if g.get("tmdb", "").isdigit() else None,
           "tvdb_id": int(g["tvdb"]) if g.get("tvdb", "").isdigit() else None,
           "imdb_id": g.get("imdb")}
    kind = item.get("type")
    if kind == "movie":
        if ids["tmdb_id"]:
            return f"movie:tmdb:{ids['tmdb_id']}", ids
        if ids["imdb_id"]:
            return f"movie:imdb:{ids['imdb_id']}", ids
    elif kind == "show":
        if ids["tvdb_id"]:
            return f"show:tvdb:{ids['tvdb_id']}", ids
        if ids["tmdb_id"]:
            return f"show:tmdb:{ids['tmdb_id']}", ids
    elif kind == "episode" and show is not None:
        sid, _ = title_id(show)
        s, e = item.get("parentIndex"), item.get("index")
        if not sid.startswith("plex:") and s is not None and e is not None:
            return f"episode:{sid.split(':', 1)[1]}:s{int(s):02d}e{int(e):02d}", ids
    return f"plex:{item.get('ratingKey')}", ids
