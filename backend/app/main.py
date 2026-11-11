import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.platform import router as platform_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import dispose_engine
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-ID", "X-CSRF-Token"],
)


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


app.include_router(v1_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(platform_router, prefix="/api/v1")
