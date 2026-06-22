from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.responses import JSONResponse


PUBLIC_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
)


def is_public_path(path: str, api_prefix: str) -> bool:
    return path in {f"{api_prefix}/health", "/health"} or path.startswith(PUBLIC_PATH_PREFIXES)


def build_auth_middleware(
    api_prefix: str, api_token: str | None
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def auth_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not api_token or request.method == "OPTIONS" or is_public_path(request.url.path, api_prefix):
            return await call_next(request)

        expected = f"Bearer {api_token}"
        if request.headers.get("authorization") != expected:
            return JSONResponse(
                status_code=401,
                content={"detail": "missing or invalid bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)

    return auth_middleware
