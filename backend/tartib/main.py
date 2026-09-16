"""App factory. Run with: uvicorn --factory tartib.main:create_app"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from tartib import ask, auth, db, items, queries
from tartib.config import Settings, load_settings
from tartib.runner import Runner

DEFAULT_STATIC = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = db.connect(settings.db_path)
        try:
            db.migrate(conn)
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

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "ai": settings.ai_enabled}

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
