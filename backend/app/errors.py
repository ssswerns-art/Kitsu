from typing import Any

from fastapi import status


class AppError(Exception):
    code: str = "APP_ERROR"
    message: str = "Application error"
    status_code: int = status.HTTP_400_BAD_REQUEST
    details: Any | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        if details is not None:
            self.details = details

        super().__init__(self.message)


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    message = "Validation error"
    status_code = status.HTTP_400_BAD_REQUEST


class NotFoundError(AppError):
    code = "NOT_FOUND"
    message = "Resource not found"
    status_code = status.HTTP_404_NOT_FOUND


class AuthError(AppError):
    code = "AUTH_ERROR"
    message = "Authentication failed"
    status_code = status.HTTP_401_UNAUTHORIZED


class PermissionError(AppError):  # type: ignore[override]
    code = "PERMISSION_DENIED"
    message = "Insufficient permissions"
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(AppError):
    code = "CONFLICT_ERROR"
    message = "Resource conflict"
    status_code = status.HTTP_409_CONFLICT


class InternalError(AppError):
    code = "INTERNAL_ERROR"
    message = "Internal server error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


ERROR_CODE_BY_STATUS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: ValidationError.code,
    status.HTTP_401_UNAUTHORIZED: AuthError.code,
    status.HTTP_403_FORBIDDEN: PermissionError.code,
    status.HTTP_404_NOT_FOUND: NotFoundError.code,
    status.HTTP_409_CONFLICT: ConflictError.code,
    status.HTTP_422_UNPROCESSABLE_ENTITY: ValidationError.code,
}


def error_payload(
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def resolve_error_code(status_code: int) -> str:
    if status_code in ERROR_CODE_BY_STATUS:
        return ERROR_CODE_BY_STATUS[status_code]
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return InternalError.code
    return "UNKNOWN_ERROR"
