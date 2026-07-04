from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from xhs_health.api.router import api_router
from xhs_health.auth import build_auth_middleware
from xhs_health.config import get_settings
from xhs_health.db import init_db
from xhs_health.services.scheduler import score_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    settings = get_settings()
    score_scheduler.configure(settings.enable_scheduler, settings.scheduler_interval_seconds)
    score_scheduler.start()
    try:
        yield
    finally:
        score_scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(build_auth_middleware(settings.api_prefix, settings.api_token or ""))

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
