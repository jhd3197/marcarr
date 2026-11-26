"""marcarr serve | scan | analyse | mcp | status."""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import sys
from pathlib import Path

from . import __version__
from . import config as cfgmod


def _logging(data_dir: Path, verbose: bool) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    fh = logging.handlers.RotatingFileHandler(data_dir / "marcarr.log", maxBytes=5_000_000,
                                              backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="marcarr", description="Know what's in every scene.")
    p.add_argument("--config", help="path to config.yaml (default: ./config.yaml or $MARCARR_CONFIG)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"marcarr {__version__}")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="run the web UI and the API")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    sub.add_parser("scan", help="read the Plex libraries once and exit")
    a = sub.add_parser("analyse", help="analyse one file (no Plex needed) and print the result")
    a.add_argument("path")
    a.add_argument("--name", help="what to call it (default: the file name)")
    a.add_argument("--steps", help="comma-separated steps (default: all)")
    m = sub.add_parser("mcp", help="MCP server over stdio, for AI clients")
    m.add_argument("--url", help="Marcarr's address (default: http://127.0.0.1:<port>)")
    sub.add_parser("status", help="print the queue and the month")
    args = p.parse_args(argv)
    cmd = args.cmd or "serve"
    cfg_path = Path(args.config) if args.config else cfgmod.default_path()

    if cmd == "mcp":
        from .mcp_server import serve as mcp_serve

        cfg = cfgmod.load(cfg_path)
        mcp_serve(args.url or f"http://127.0.0.1:{cfg.server.port}")
        return 0

    cfg = cfgmod.load(cfg_path)
    _logging(cfg.data_dir, args.verbose)

    if cmd == "serve":
        import uvicorn

        from .core import Core
        from .server import create_app

        if not cfg_path.is_file():
            cfgmod.save(cfg, cfg_path)
        core = Core(cfg, cfg_path)
        app = create_app(core)
        host = args.host or cfg.server.host
        port = args.port or cfg.server.port
        logging.getLogger("marcarr").info("Marcarr %s on http://%s:%s", __version__, host, port)
        uvicorn.run(app, host=host, port=port, log_level="warning")
        return 0

    from .core import Core

    core = Core(cfg, cfg_path, start_worker=False)
    try:
        if cmd == "scan":
            job = core.library.submit_scan()
            core.worker.run_pending("light")
            print(json.dumps(core.jobs.get(job["id"])["result"], indent=2))
        elif cmd == "analyse":
            vid = _register(core, Path(args.path), args.name)
            steps = [x.strip() for x in args.steps.split(",")] if args.steps else None
            core.pipeline.submit(vid, steps)
            core.worker.run_pending("heavy")
            from .views import Views

            v = Views(core).video_view(core.store.video(vid))
            print(json.dumps({"video": vid, "steps": v["step_info"], "scenes": v["scenes"],
                              "shots": v["shots"], "lines": v["lines"]}, indent=2))
        elif cmd == "status":
            print(json.dumps({"queue": core.jobs.depth(), "month_cost": core.store.month_cost(),
                              "review": core.store.review_count()}, indent=2))
    finally:
        core.close()
    return 0


def _register(core: object, path: Path, name: str | None) -> str:
    """A file outside Plex gets a local title so it can be analysed on its own."""
    from .store import slug

    if not path.is_file():
        raise SystemExit(f"no such file: {path}")
    c = core  # type: ignore[assignment]
    tid = "local:" + slug(name or path.stem)
    c.store.upsert_title({"id": tid, "type": "movie", "name": name or path.stem,  # type: ignore[attr-defined]
                          "sort_name": (name or path.stem).lower(), "file": str(path)})
    return c.library.add_file(tid, str(path))  # type: ignore[attr-defined]


if __name__ == "__main__":
    sys.exit(main())
