"""One error format for the whole API: {"detail", "code", "errors"?}  (docs/API_CONTRACT.md section 1).

TEMPORARY STUB written by Member 2. Owner: Member 1 (Faizan).
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")

_STATUS_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
}


class AppError(Exception):
    def __init__(self, status_code: int, code: str, detail: str, errors: list[dict] | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.errors = errors


def _body(detail: str, code: str, errors: list[dict] | None = None) -> dict:
    body = {"detail": detail, "code": code}
    if errors:
        body["errors"] = errors
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_body(exc.detail, exc.code, exc.errors))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path", "header")),
                "message": str(e.get("msg", "Invalid value")),
            }
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content=_body("Validation failed", "validation_error", errors))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "error")
        return JSONResponse(status_code=exc.status_code, content=_body(str(exc.detail), code))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content=_body("Internal server error", "internal_error"))
