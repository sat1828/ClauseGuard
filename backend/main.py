"""
ClauseGuard FastAPI Application
================================
Entry point using the modern lifespan context manager pattern
(replaces deprecated @app.on_event which FastAPI removed in 0.109+).
"""

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings

# Import models so Alembic detects them in autogenerate
from models import contract as _contract_models  # noqa: F401
from models import user as _user_models  # noqa: F401

from routers import analysis, chat, contracts

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan — runs startup then yields to serve requests,
    then runs shutdown. Replaces deprecated @app.on_event.
    """
    # ── Startup ───────────────────────────────────────────────────────────
    logger.info(
        "clauseguard_starting",
        version=settings.APP_VERSION,
        pipeline_version=settings.PIPELINE_VERSION,
        environment=settings.ENVIRONMENT,
        claude_model=settings.CLAUDE_MODEL,
    )

    # Auto-create tables in dev (production uses Alembic migrations)
    if settings.ENVIRONMENT in ("development", "staging"):
        from database import create_tables
        await create_tables()
        logger.info("database_tables_ready")

    yield  # Application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("clauseguard_shutting_down")


app = FastAPI(
    title="ClauseGuard API",
    description="AI-powered contract risk analysis. Not legal advice.",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://clauseguard.vercel.app",
]
if settings.BACKEND_URL not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(settings.BACKEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - start:.4f}s"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again.",
            "error": str(exc) if settings.DEBUG else "Internal server error",
        },
    )


app.include_router(contracts.router)
app.include_router(analysis.router)
app.include_router(chat.router)


@app.get("/health", tags=["ops"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "pipeline_version": settings.PIPELINE_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["ops"])
async def root():
    return {
        "app": "ClauseGuard API",
        "version": settings.APP_VERSION,
        "disclaimer": (
            "ClauseGuard is not a law firm and does not provide legal advice. "
            "All analysis is for informational purposes only."
        ),
    }
