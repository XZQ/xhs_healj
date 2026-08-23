import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from xhs_health.api.router import api_router
from xhs_health.auth import build_auth_middleware
from xhs_health.config import get_settings
from xhs_health.db import init_db
from xhs_health.services.scheduler import score_scheduler


def _json_safe(value: Any) -> Any:
    """Make a validation-error detail serializable: a non-finite float echoed
    from a rejected NaN/Infinity body crashes Starlette's strict JSON encoder
    (allow_nan=False), turning a 422 into a 500."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, BaseException):
        return str(value)
    return value


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

    @app.exception_handler(RequestValidationError)
    async def sanitized_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": _json_safe(exc.errors())})

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
