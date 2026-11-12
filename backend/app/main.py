import asyncio
import logging
import re
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.platform import router as platform_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import check_database_connection, dispose_engine
from app.services.ai_provider import close_openai_client

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s in %s mode", settings.app_name, settings.environment)
    yield
    await close_openai_client()
    await dispose_engine()
    logger.info("Stopping %s", settings.app_name)


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


def _safe_request_path(path: str) -> str:
    """Remove bearer-like public share tokens from application logs."""
    marker = "/api/v1/shared/"
    if marker in path:
        prefix, _, _token = path.partition(marker)
        return f"{prefix}{marker}[redacted]"
    return path


@app.middleware("http")
async def security_and_request_context(request: Request, call_next):
    """Attach a safe correlation ID and baseline security headers to every response.

    The request ID is deliberately restricted to a short opaque value and is never
    populated from request bodies, cookies, or query strings. Logging includes only
    method/path/status/timing so credentials and private content are not recorded.
    """
    supplied = request.headers.get("X-Request-ID", "")
    request_id = supplied if re.fullmatch(r"[A-Za-z0-9._:-]{1,96}", supplied) else str(uuid4())
    request.state.correlation_id = request_id
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    logger.info(
        "request method=%s path=%s status=%s latency_ms=%.2f request_id=%s",
        request.method,
        _safe_request_path(request.url.path),
        response.status_code,
        (perf_counter() - started) * 1000,
        request_id,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database request failed: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database unavailable. Check DATABASE_URL and run migrations."},
    )


@app.get("/health", tags=["health"])
async def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "pychat-api"}


@app.get("/health/ready", tags=["health"])
async def readiness_health() -> JSONResponse:
    """Bounded readiness probe for Railway; it never calls paid providers."""
    components: dict[str, str] = {}
    try:
        await asyncio.wait_for(check_database_connection(), timeout=2)
        components["database"] = "ok"
    except Exception:  # noqa: BLE001 - readiness must return a safe generic status
        components["database"] = "error"

    if settings.redis_url:
        try:
            import redis.asyncio as redis

            client = redis.from_url(
                settings.redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            try:
                await asyncio.wait_for(client.ping(), timeout=2)
            finally:
                await client.aclose()
            components["redis"] = "ok"
        except Exception:  # noqa: BLE001 - do not expose provider details
            components["redis"] = "error"
    else:
        components["redis"] = "unconfigured"

    ready = components["database"] == "ok" and components["redis"] != "error"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "components": components},
        headers={"Cache-Control": "no-store"},
    )


app.include_router(v1_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(platform_router, prefix="/api/v1")
