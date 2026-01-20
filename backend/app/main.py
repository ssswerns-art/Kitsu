import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
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
from .api import router as api_router
from .parser.jobs.autoupdate import parser_autoupdate_scheduler
from .routers import (
    anime,
    auth,
    episodes,
    favorites,
    releases,
    search,
    watch,
)
from .utils.health import check_database_connection
from .utils.startup import run_optional_startup_tasks, run_required_startup_checks

AVATAR_DIR = Path(__file__).resolve().parent.parent / "uploads" / "avatars"
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
    logger.info("Starting application")
    if settings.debug:
        logger.warning("DEBUG=true — do not use in production")

    await run_required_startup_checks(engine)
    await run_optional_startup_tasks()
    await parser_autoupdate_scheduler.start()

    yield

    await parser_autoupdate_scheduler.stop()
    await default_job_runner.stop()


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
    api_router,
]

for router in routers:
    app.include_router(router)

app.include_router(search.router, tags=["Search"])

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


def _extract_canonical_error(detail: object) -> dict[str, object] | None:
    if not isinstance(detail, dict):
        return None
    error = detail.get("error")
    if not isinstance(error, dict):
        return None
    if not isinstance(error.get("code"), str) or not isinstance(
        error.get("message"), str
    ):
        return None
    if "details" not in error:
        return {"error": {**error, "details": None}}
    return detail


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    _log_error(request, exc.status_code, exc.code, exc.message, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(
    request: Request, exc: HTTPException | StarletteHTTPException
) -> JSONResponse:
    payload = _extract_canonical_error(exc.detail)
    if payload is not None:
        error = payload["error"]
        code = error.get("code", resolve_error_code(exc.status_code))
        message = error.get("message", "")
        _log_error(request, exc.status_code, str(code), str(message))
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


@app.exception_handler(StarletteHTTPException)
async def handle_starlette_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return await handle_http_exception(request, exc)


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
