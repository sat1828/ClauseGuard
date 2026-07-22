import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import init_db
from app.job_queue import start_workers, stop_workers
from app.routers import auth, documents, billing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("clauseguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await start_workers()
    logger.info("ClauseGuard backend started.")
    yield
    await stop_workers()
    logger.info("ClauseGuard backend stopped.")


app = FastAPI(title="ClauseGuard API", version="1.0.0", lifespan=lifespan)

# CORS: wide open for local dev. LOCK THIS DOWN before deploying publicly —
# replace allow_origins with your actual frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Minimal in-process rate limiter (audit finding: upload endpoint had
# no rate limiting at all). Per-IP sliding window. Good enough for a single
# instance; swap for Redis-backed limiting if you ever run >1 process. ----
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 20
_request_log: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/documents/upload"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        log = _request_log[client_ip]
        while log and now - log[0] > _RATE_LIMIT_WINDOW_SECONDS:
            log.popleft()
        if len(log) >= _RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": {"code": "RATE_LIMITED", "message": "Too many uploads. Try again in a minute."}},
            )
        log.append(now)
    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "VALIDATION_ERROR", "message": str(exc.errors())}},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(billing.router)
