"""Uniform error shape: {detail, code, errors?} (API_CONTRACT.md section 1)."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")

_DEFAULT_CODES = {
    400: "bad_request", 401: "not_authenticated", 403: "forbidden", 404: "not_found",
    405: "method_not_allowed", 409: "conflict", 413: "payload_too_large", 429: "too_many_attempts", 422: "validation_error",
}


class ApiError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, detail: str, *, code: str | None = None, errors: list[dict] | None = None):
        super().__init__(detail)
        self.detail = detail
        if code:
            self.code = code
        self.errors = errors


class BadRequest(ApiError):
    status_code, code = 400, "bad_request"


class NotAuthenticated(ApiError):
    status_code, code = 401, "not_authenticated"


class Forbidden(ApiError):
    status_code, code = 403, "forbidden"


class NotFound(ApiError):
    status_code, code = 404, "not_found"

    def __init__(self, detail: str = "Record not found"):
        super().__init__(detail)


class TooManyRequests(ApiError):
    status_code, code = 429, "too_many_attempts"


class Conflict(ApiError):
    status_code, code = 409, "conflict"


class PayloadTooLarge(ApiError):
    status_code, code = 413, "payload_too_large"


class ValidationFailed(ApiError):
    status_code, code = 422, "validation_error"

    def __init__(self, detail: str = "Validation failed", errors: list[dict] | None = None):
        super().__init__(detail, errors=errors)


def field_error(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def _body(detail: str, code: str, errors=None) -> dict:
    out = {"detail": detail, "code": code}
    if errors:
        out["errors"] = errors
    return out


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return JSONResponse(_body(exc.detail, exc.code, exc.errors), status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = _DEFAULT_CODES.get(exc.status_code, "error")
        return JSONResponse(_body(str(exc.detail), code), status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = []
        for e in exc.errors():
            loc = [str(p) for p in e["loc"] if p not in ("body", "query", "path")]
            msg = e["msg"].removeprefix("Value error, ")
            errors.append(field_error(".".join(loc) or "body", msg))
        return JSONResponse(_body("Validation failed", "validation_error", errors), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse(_body("Internal server error", "server_error"), status_code=500)
