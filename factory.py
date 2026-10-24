"""App factory: builds an app from settings. Tests call it with their own Settings; uvicorn uses app.main."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .channels import make_notifier
from .channels.voice import TwilioMediaFetcher, make_transcriber
from .config import Settings, get_settings
from .db import make_repository
from .files import ensure_stub_files
from .routers import all_routers
from .seed import seed_demo
from .tinyfish import make_web_client


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="KhetKaaj", version=__version__)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"]
    )

    app.state.settings = settings
    app.state.repo = make_repository(settings)
    app.state.web = make_web_client(settings, app.state.repo)
    app.state.notifier = make_notifier(settings)
    app.state.transcriber = make_transcriber(settings)
    app.state.media_fetcher = TwilioMediaFetcher(settings)
    seed_demo(app.state.repo, settings)
    ensure_stub_files(settings)

    for router in all_routers():
        app.include_router(router)
    return app
