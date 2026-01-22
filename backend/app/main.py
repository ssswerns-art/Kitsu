import logging
import os
from typing import cast
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import (
    IntegrityError,
    MultipleResultsFound,
    NoResultFound,
    ProgrammingError,
    SQLAlchemyError,
)

from .background import default_job_runner
from .config import settings
from .database import engine
from .errors import (
    AppError,
    AuthError,
    ConflictError,
    InternalError,
    NotFoundError,
    PermissionError,
    ValidationError,
    error_payload,
    resolve_error_code,
)
from .admin import router as admin_router
from .api import router as api_router
from .parser.admin import router as parser_admin_router
from .parser.jobs.autoupdate import parser_autoupdate_scheduler
from .routers import (
    anime,
    auth,
    episodes,
    favorites,
    releases,
    watch,
)
from .utils.health import check_database_connection
from .utils.startup import run_optional_startup_tasks, run_required_startup_checks

AVATAR_DIR = Path(__file__).resolve().parent.parent / "uploads" / "avatars"
# Create avatar directory early to allow StaticFiles mount at import time
# This is a minimal side effect - just directory creation with exist_ok=True
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()


def _resolve_log_level(value: str) -> int:
    level = logging.getLevelName(value)
    return level if isinstance(level, int) else logging.INFO


log_level = _resolve_log_level(log_level_name)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
logger = logging.getLogger("kitsu")
logger.setLevel(log_level)


def _health_response(status_text: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"status": status_text})

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with proper error handling and cleanup."""
    logger.info("Starting application")
    
    # Import Redis utilities here to avoid circular imports
    from .infrastructure.redis import init_redis, close_redis, get_redis
    
    # Track what was initialized for cleanup
    redis_initialized = False
    scheduler_started = False
    
    try:
        # Validate settings early (ISSUE #6 - deferred from import time)
        if settings.debug:
            logger.warning("DEBUG=true — do not use in production")
        
        # ISSUE #1: Wrap all startup in try/except for guaranteed cleanup
        # Initialize Redis for distributed coordination
        await init_redis(settings.redis_url)
        redis_initialized = True
        logger.info("Redis initialized for distributed coordination")
        
        # ISSUE #2: Verify Redis connection with ping
        try:
            redis_client = get_redis()
            redis = await redis_client._ensure_connected()
            # Perform actual ping to verify connectivity
            await redis.ping()
            logger.info("Redis connection verified with ping")
        except Exception as exc:
            logger.error("Redis ping failed - Redis is not accessible", exc_info=exc)
            raise RuntimeError("Redis connection failed. Ensure Redis is running and accessible at %s" % settings.redis_url) from exc

        # Run database checks
        await run_required_startup_checks(engine)
        await run_optional_startup_tasks()
        
        # Start parser autoupdate scheduler (uses distributed lock)
        await parser_autoupdate_scheduler.start()
        scheduler_started = True
        logger.info("Parser autoupdate scheduler started")

        yield

    except Exception as exc:
        # ISSUE #1: Log startup failure and perform cleanup before re-raising
        logger.error("Application startup failed", exc_info=exc)
        raise
        
    finally:
        # ISSUE #3: Cleanup with individual try/except blocks
        # Each step is isolated so one failure doesn't block others
        logger.info("Starting application shutdown")
        
        # Stop parser scheduler
        if scheduler_started:
            try:
                await parser_autoupdate_scheduler.stop()
                logger.info("Parser autoupdate scheduler stopped")
            except Exception as exc:
                logger.error("Error stopping parser scheduler", exc_info=exc)
        
        # Stop default job runner
        try:
            await default_job_runner.stop()
            logger.info("Default job runner stopped")
        except Exception as exc:
            logger.error("Error stopping default job runner", exc_info=exc)
        
        # Close Redis connection
        if redis_initialized:
            try:
                await close_redis()
                logger.info("Redis connection closed")
            except Exception as exc:
                logger.error("Error closing Redis connection", exc_info=exc)
        
        logger.info("Application shutdown complete")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

# Convert allowed_origins to a set for O(1) lookup performance in middleware
_allowed_origins_set = set(settings.allowed_origins)


class OptionsPreflightMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle OPTIONS preflight requests before they reach CORSMiddleware.
    This prevents 400 errors for disallowed origins by returning 204 for all OPTIONS requests.
    Allowed origins still get proper CORS headers from this middleware.
    """
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            origin = request.headers.get("origin")
            response = Response(status_code=status.HTTP_204_NO_CONTENT)
            
            # Add CORS headers for allowed origins (O(1) lookup)
            if origin and origin in _allowed_origins_set:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
                
                # Handle Access-Control-Allow-Headers:
                # 1. If client sends Access-Control-Request-Headers, echo it back
                # 2. Otherwise, use safe allowlist
                requested_headers = request.headers.get("access-control-request-headers")
                if requested_headers:
                    response.headers["Access-Control-Allow-Headers"] = requested_headers
                else:
                    response.headers["Access-Control-Allow-Headers"] = "authorization, content-type"
                
                response.headers["Access-Control-Max-Age"] = "600"
                # Add Vary: Origin to indicate response varies by Origin header
                response.headers["Vary"] = "Origin"
            
            return response
        
        return await call_next(request)


# Add CORSMiddleware first (runs last), then OptionsPreflightMiddleware (runs first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

app.add_middleware(OptionsPreflightMiddleware)

app.mount(
    "/media/avatars",
    StaticFiles(directory=AVATAR_DIR, html=False),
    name="avatars",
)

routers = [
    auth.router,
    anime.router,
    releases.router,
    episodes.router,
    favorites.router,
    watch.router,
    admin_router.router,
    parser_admin_router.router,
    api_router,
]

for router in routers:
    app.include_router(router)

SAFE_HTTP_MESSAGES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: ValidationError.message,
    status.HTTP_401_UNAUTHORIZED: AuthError.message,
    status.HTTP_403_FORBIDDEN: PermissionError.message,
    status.HTTP_404_NOT_FOUND: NotFoundError.message,
    status.HTTP_409_CONFLICT: ConflictError.message,
    status.HTTP_422_UNPROCESSABLE_ENTITY: ValidationError.message,
}


def _log_error(request: Request, status_code: int, code: str, message: str, exc: Exception | None = None) -> None:
    request_id = request.headers.get("x-request-id")
    log_message = f"[{code}] path={request.url.path} request_id={request_id or 'n/a'} message={message}"
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(log_message, exc_info=exc)
    else:
        logger.warning(log_message, exc_info=exc)


def _ensure_canonical_error_format(detail: object) -> dict[str, object] | None:
    """Return a canonical error envelope if the detail already follows the contract."""
    if not isinstance(detail, dict):
        return None
    error = detail.get("error")
    if not isinstance(error, dict):
        return None
    if not isinstance(error.get("code"), str) or not isinstance(
        error.get("message"), str
    ):
        return None
    return {
        "error": {
            "code": error["code"],
            "message": error["message"],
            "details": error.get("details"),
        }
    }


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    _log_error(request, exc.status_code, exc.code, exc.message, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    payload = _ensure_canonical_error_format(exc.detail)
    if payload is not None:
        error = cast(dict[str, str], payload["error"])
        _log_error(request, exc.status_code, error["code"], error["message"])
        return JSONResponse(status_code=exc.status_code, content=payload)
    safe_message = SAFE_HTTP_MESSAGES.get(
        exc.status_code,
        InternalError.message if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR else "Request failed",
    )
    detail = exc.detail
    detail_message = detail if isinstance(detail, str) else ""
    log_message = detail_message.strip() or safe_message
    code = resolve_error_code(exc.status_code)
    _log_error(request, exc.status_code, code, log_message)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, safe_message, detail),
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    message = "Request validation failed"
    _log_error(request, status.HTTP_422_UNPROCESSABLE_ENTITY, ValidationError.code, message, exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(ValidationError.code, message, exc.errors()),
    )


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    log_message = str(exc).strip() or "Invalid request"
    _log_error(request, status.HTTP_400_BAD_REQUEST, ValidationError.code, log_message, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_payload(ValidationError.code, "Invalid request", log_message),
    )


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    message = "Request could not be completed due to a conflict"
    _log_error(request, status.HTTP_409_CONFLICT, ConflictError.code, message, exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_payload(ConflictError.code, message, str(exc)),
    )


@app.exception_handler(ProgrammingError)
async def handle_programming_error(request: Request, exc: ProgrammingError) -> JSONResponse:
    message = "Database not initialized. Ensure migrations are applied."
    _log_error(request, status.HTTP_500_INTERNAL_SERVER_ERROR, InternalError.code, message, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload(InternalError.code, message, str(exc)),
    )


@app.exception_handler(NoResultFound)
async def handle_no_result_found(request: Request, exc: NoResultFound) -> JSONResponse:
    message = "Requested resource was not found"
    _log_error(request, status.HTTP_404_NOT_FOUND, NotFoundError.code, message, exc)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_payload(NotFoundError.code, message, str(exc)),
    )


@app.exception_handler(MultipleResultsFound)
async def handle_multiple_results_found(
    request: Request, exc: MultipleResultsFound
) -> JSONResponse:
    message = "Multiple resources found where one expected"
    _log_error(request, status.HTTP_409_CONFLICT, ConflictError.code, message, exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_payload(ConflictError.code, message, str(exc)),
    )


@app.exception_handler(Exception)
async def handle_unhandled_exception(
    request: Request, exc: Exception
) -> JSONResponse:
    _log_error(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        InternalError.code,
        InternalError.message,
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload(InternalError.code, InternalError.message, str(exc)),
    )




@app.get("/health", tags=["health"])
async def healthcheck() -> Response:
    try:
        # Keep health probe lightweight; metadata logging is handled at startup
        await check_database_connection(engine, include_metadata=False)
    except SQLAlchemyError as exc:
        logger.error("Healthcheck database probe failed: %s", exc)
        return _health_response("error", status.HTTP_503_SERVICE_UNAVAILABLE)

    logger.debug("Healthcheck passed")
    return _health_response("ok", status.HTTP_200_OK)
