"""The FastAPI app: /api/v1 for the UI and other apps, the built UI at /."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from . import __version__
from .core import Core
from .errors import ConfigError, MarcarrError, NotFoundError
from .routes import common, review, system, titles

log = logging.getLogger("marcarr.server")
UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"
PACKAGED_UI = Path(__file__).resolve().parent / "ui"


def create_app(core: Core) -> FastAPI:
    common.set_core(core)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> Any:
        yield
        core.close()

    app = FastAPI(title="Marcarr", version=__version__, lifespan=lifespan,
                  docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json", redoc_url=None)

    @app.exception_handler(NotFoundError)
    async def _nf(_r: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(ConfigError)
    async def _cfg(_r: Request, exc: ConfigError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(MarcarrError)
    async def _err(_r: Request, exc: MarcarrError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    for r in (system.router, titles.router, review.router):
        app.include_router(r, prefix="/api/v1")

    @app.get("/api/{rest:path}", include_in_schema=False)
    def api_404(rest: str) -> Response:
        return JSONResponse({"detail": f"no such endpoint: /api/{rest}"}, status_code=404)

    dist = UI_DIST if UI_DIST.is_dir() else PACKAGED_UI
    if dist.is_dir():
        @app.get("/{path:path}", include_in_schema=False)
        def ui(path: str) -> Response:
            f = (dist / path).resolve()
            if path and f.is_file() and dist.resolve() in f.parents:
                cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
                return FileResponse(f, headers={"Cache-Control": cache})
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/", include_in_schema=False)
        def no_ui() -> Response:
            return Response("Marcarr is running, but the UI is not built: cd ui && npm run build\n",
                            media_type="text/plain")

    return app
