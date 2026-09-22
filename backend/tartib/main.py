"""App factory. Run with: uvicorn --factory tartib.main:create_app"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from tartib import (
    ask,
    auth,
    briefs,
    captures,
    db,
    items,
    links,
    pick,
    push,
    queries,
    sessions,
    spaces,
)
from tartib.config import Settings, load_settings
from tartib.reminders import Reminders
from tartib.runner import Runner
from tartib.sessions import Sessions
from tartib.spaces import seed_spaces
from tartib.store import list_spaces, reconcile_spaces, reindex_links

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
            # The link tables are an index of the text, rebuilt whole: cheap at this size, and
            # it means a key rule changed in code applies to every item on the next start.
            reindex_links(conn)
        finally:
            conn.close()
        runner = Runner(settings)
        app.state.runner = runner
        await runner.start()
        # Without VAPID keys there is nothing to sign a push with, so the loop stays off
        # rather than marking reminders sent that nobody could have received.
        reminders = Reminders(settings) if settings.push_enabled else None
        if reminders is not None:
            try:
                push.check_key(settings)
            except Exception as e:  # a bad key must not quietly consume every reminder
                log.error("TARTIB_VAPID_PRIVATE is unusable (%s); reminders stay off", e)
                reminders = None
        app.state.reminders = reminders
        # What the UI is told. With the loop off, offering to enable reminders would earn a
        # card that says "on" over something that can never fire.
        app.state.push_ready = reminders is not None
        # Sessions are logged whether or not anything can be pushed; only the buzz at the end
        # needs push, and `broadcast` over zero subscriptions is a no-op.
        clock = Sessions(settings)
        app.state.sessions = clock
        try:
            if reminders is not None:
                await reminders.start()
            await clock.start()
            yield
        finally:
            await clock.stop()
            if reminders is not None:
                await reminders.stop()
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
    app.include_router(push.router)
    app.include_router(sessions.router)
    app.include_router(pick.router)
    app.include_router(links.router)

    # Everything this app loads, it ships. Fonts are bundled, there is no CDN and no analytics,
    # so the policy can be tight. `img-src 'self' data:` is the line that matters: item text,
    # Ask answers and space briefs are written by the model from text that may not be the
    # owner's, and a remote image is the simplest way for what the model saw to leave the
    # device. Markdown stopped rendering remote images on 2026-09-22; this makes it structural
    # rather than a property of one renderer.
    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; font-src 'self'; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # The files that decide which version runs must never be cached by anything in between.
        # Tartib used to send no Cache-Control on them, so Cloudflare applied its own default --
        # cache at the edge for four hours -- and after a deploy a phone's update check fetched
        # the *old* service worker from the edge, saw nothing new, and never offered the reload.
        # Found 2026-09-22 when v2.0 had to be deleted and re-added to take. `no-cache` still
        # allows a conditional request, so an unchanged file costs a 304, not a download.
        # Vite's hashed assets under /assets/ are left alone: their names change with their
        # contents, so caching them forever is correct.
        if request.url.path in ("/", "/index.html", "/sw.js", "/manifest.webmanifest"):
            response.headers["Cache-Control"] = "no-cache"
        return response

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
