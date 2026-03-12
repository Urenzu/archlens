from typing import Optional, Any


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "detail": self.detail,
        }


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


def raise_not_found(resource: str, id: Any) -> None:
    raise NotFoundError(f"{resource} not found", detail={"id": id})


def raise_validation(field: str, reason: str) -> None:
    raise ValidationError(f"Invalid field: {field}", detail={"field": field, "reason": reason})


def raise_auth(reason: str = "Authentication required") -> None:
    raise AuthError(reason)


def raise_forbidden(action: str, resource: str) -> None:
    raise ForbiddenError(f"Cannot {action} {resource}")


def format_error_response(exc: Exception) -> tuple[dict, int]:
    if isinstance(exc, AppError):
        return exc.to_dict(), exc.status_code
    return {"error": "internal_error", "message": str(exc)}, 500


def is_client_error(exc: Exception) -> bool:
    if isinstance(exc, AppError):
        return 400 <= exc.status_code < 500
    return False


def is_retryable(exc: Exception) -> bool:
    retryable_codes = {"rate_limited", "internal_error"}
    if isinstance(exc, AppError):
        return exc.code in retryable_codes
    return True
