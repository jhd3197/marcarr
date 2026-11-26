"""What every route module shares: the Core, the views, scopes, media caching."""

from __future__ import annotations

import hashlib
import ipaddress
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request

from ..core import Core
from ..errors import MarcarrError, NotFoundError
from ..views import Views

_core: Core | None = None
_views: Views | None = None


def set_core(core: Core) -> None:
    global _core, _views
    _core = core
    _views = Views(core)


def core() -> Core:
    if _core is None:
        raise RuntimeError("the app has no Core yet")
    return _core


def views() -> Views:
    if _views is None:
        raise RuntimeError("the app has no Core yet")
    return _views


def _local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in ("testclient", "localhost")


def scope(name: str | None) -> Callable[[Request], Any]:
    """A dependency: the caller may do *name* (None: the web UI only, never a key)."""

    def check(request: Request) -> dict[str, Any] | None:
        c = core()
        key = request.headers.get("X-Api-Key") or request.query_params.get("apikey")
        if key:
            who = c.keys.check(key)
            if who is None:
                raise HTTPException(401, "unknown API key")
            if name is None:
                raise HTTPException(403, "this needs the Marcarr web page, not an API key")
            if name not in who["scopes"] and not (name == "read"):
                raise HTTPException(403, f"this key may not {name}")
            request.state.app_name = who["name"]
            return who
        if c.cfg.server.require_key and not _local(request) and not _same_origin(request):
            raise HTTPException(401, "this Marcarr needs an API key (X-Api-Key)")
        request.state.app_name = None
        return None

    return check


def _same_origin(request: Request) -> bool:
    """A call from Marcarr's own pages (the browser sends its origin or referer)."""
    host = request.headers.get("host", "")
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    return bool(host) and (f"//{host}/" in origin + "/")


READ = Depends(scope("read"))
PROPOSE = Depends(scope("propose"))
REVIEW = Depends(scope("review"))
RUN = Depends(scope("run"))
UI = Depends(scope(None))


def source_of(request: Request, default: str = "person") -> str:
    """Who is making a change: the app's name for a key, else a person."""
    name = getattr(request.state, "app_name", None)
    if not name:  # no key: a client may still say what it is (the MCP server does)
        name = request.headers.get("X-Marcarr-Client", "").strip()[:40] or None
    return (name or default).lower()


# -- media files ---------------------------------------------------------------------
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def cache_path(kind: str, *parts: Any, ext: str = "jpg") -> Path:
    raw = "|".join(str(x) for x in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    out = core().data_dir / "cache" / kind / f"{digest}.{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def once(path: Path, make: Callable[[Path], None]) -> Path:
    """Make a cached file at most once at a time."""
    with _locks_lock:
        lock = _locks.setdefault(str(path), threading.Lock())
    with lock:
        if not path.is_file():
            make(path)
    return path


def video_file(vid: str) -> tuple[dict[str, Any], str]:
    v = core().store.video(vid)
    if not Path(v["path"]).is_file():
        raise NotFoundError("the video file is not on disk")
    return v, v["path"]


def frame_file(vid: str, t: float, height: int = 240) -> Path:
    from prompture.media.understand import extract_frame

    v, path = video_file(vid)
    height = max(90, min(int(height), 1080))
    t = max(0.0, round(float(t), 2))
    out = cache_path("frames", v["content_key"], t, height)

    def make(p: Path) -> None:
        tmp = p.with_suffix(".part")
        tmp.write_bytes(extract_frame(path, t, height=height))
        tmp.replace(p)

    return once(out, make)


MAX_CLIP = 300.0


def clip_file(vid: str, a: float, b: float) -> Path:
    v, path = video_file(vid)
    if b <= a:
        raise MarcarrError("the clip must end after it starts")
    b = min(b, a + MAX_CLIP)
    out = cache_path("clips", v["content_key"], round(a, 2), round(b, 2), ext="mp4")
    ffmpeg = core().cfg.ffmpeg.binary

    def make(p: Path) -> None:
        tmp = p.with_suffix(".tmp.mp4")
        proc = subprocess.run(  # noqa: S603 - argv list
            [ffmpeg, "-v", "error", "-nostdin", "-y", "-ss", f"{a:.3f}", "-i", path, "-t",
             f"{b - a:.3f}", "-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale=-2:480",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ac", "2", "-b:a", "128k", "-sn", "-movflags", "+faststart",
             str(tmp)], capture_output=True, timeout=900, check=False)
        if proc.returncode:
            tmp.unlink(missing_ok=True)
            raise MarcarrError("could not cut the clip: "
                               + (proc.stderr or b"").decode("utf-8", "replace")[-300:])
        tmp.replace(p)

    return once(out, make)


def fetch_image(url: str, kind: str, headers: dict[str, str] | None = None) -> Path | None:
    """An image from the network, cached on disk (None when it can't be had)."""
    out = cache_path(kind, url)
    if out.is_file():
        return out
    try:
        r = core().session.get(url, timeout=20, headers=headers or {})
    except Exception:  # noqa: BLE001 - no image is not an error
        return None
    if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
        return None
    out.write_bytes(r.content)
    return out
