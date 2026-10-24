"""Errors and the single JSON error format of the API.

Services raise the domain errors below (never HTTPException). The handlers registered in `register_error_handlers`
turn every error, including validation errors and unexpected crashes, into the same response body:

    {"code": "not_found", "message": "Application not found", "details": {...}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class AppError(Exception):
    """Base class for errors the API reports to clients on purpose."""

    status_code = 500
    code = "internal_error"
    headers: dict[str, str] | None = None  # extra response headers, e.g. WWW-Authenticate on 401

    def __init__(self, message: str, *, details: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if headers is not None:  # per-error headers (e.g. Retry-After) on top of the class default
            self.headers = {**(type(self).headers or {}), **headers}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PaymentRequiredError(AppError):
    """The plan doesn't cover this (e.g. the month's free packs are used up)."""

    status_code = 402
    code = "payment_required"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    headers = {"WWW-Authenticate": "Bearer"}  # tells clients which kind of credentials to send


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class InvalidInputError(AppError):
    """The request is well-formed but its content can't be accepted (e.g. an inconsistent profile)."""

    status_code = 422
    code = "invalid_input"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UpstreamError(AppError):
    """An outside service we depend on (e.g. the LLM) failed or returned something unusable."""

    status_code = 502
    code = "upstream_error"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


def _response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, details=details)
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True), headers=headers)


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return _response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Report where and what, never the submitted values (they may contain personal data).
    problems = [{"field": ".".join(str(p) for p in err["loc"]), "problem": err["msg"]} for err in exc.errors()]
    return _response(422, "validation_error", "The request is invalid", {"errors": problems})


async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Framework errors such as unknown routes (404) or wrong methods (405).
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return _response(exc.status_code, code, str(exc.detail))


async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", type(exc).__name__)
    return _response(500, "internal_error", "Something went wrong on our side")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
