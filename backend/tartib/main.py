"""App factory. Run with: uvicorn --factory tartib.main:create_app"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from tartib import ask, auth, briefs, captures, db, items, queries, spaces
from tartib.config import Settings, load_settings
from tartib.runner import Runner
from tartib.spaces import seed_spaces
from tartib.store import list_spaces, reconcile_spaces

DEFAULT_STATIC = Path(__file__).resolve().parent.parent / "static"
log = logging.getLogger("tartib")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = db.connect(settings.db_path)
        try:
            db.migrate(conn)
            seeded = seed_spaces(conn, settings.spaces)
            if seeded:
                log.info("seeded %d spaces from TARTIB_SPACES", seeded)
            moved = reconcile_spaces(conn, list_spaces(conn))
            if moved:
                log.warning("%d items had unconfigured spaces; moved to Needs Attention", moved)
        finally:
            conn.close()
        runner = Runner(settings)
        app.state.runner = runner
        await runner.start()
        try:
            yield
        finally:
            await runner.stop()

    app = FastAPI(title="Tartib", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.include_router(auth.router)
    app.include_router(items.router)
    app.include_router(queries.router)
    app.include_router(ask.router)
    app.include_router(captures.router)
    app.include_router(briefs.router)
    app.include_router(spaces.router)

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "ai": settings.ai_enabled,
            "fallback": bool(settings.ai_fallback_command),
        }

    static_dir = (Path(settings.static_dir) if settings.static_dir else DEFAULT_STATIC).resolve()
    if static_dir.is_dir():
        index = static_dir / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404)
            candidate = (static_dir / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(static_dir):
                return FileResponse(candidate)
            return FileResponse(index)

    return app
