"""Global FastAPI exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register API-wide exception handlers with a consistent error shape."""

    @app.exception_handler(AppError)
    async def handle_app_error(
        request: Request,
        exc: AppError,
    ) -> JSONResponse:
        _log_error(request=request, status_code=exc.status_code, exc=exc)
        return _error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        _log_error(request=request, status_code=422, exc=exc)
        return _error_response(
            status_code=422,
            code="validation_error",
            message=_format_validation_message(exc.errors()),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        _log_error(request=request, status_code=exc.status_code, exc=exc)
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _error_response(
            status_code=exc.status_code,
            code="http_error",
            message=detail,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        _log_error(request=request, status_code=500, exc=exc)
        return _error_response(
            status_code=500,
            code="internal_server_error",
            message="An unexpected error occurred.",
        )


def _error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _log_error(*, request: Request, status_code: int, exc: Exception) -> None:
    message = "%s %s returned %s"
    args = (request.method, request.url.path, status_code)
    if status_code >= 500:
        logger.error(message, *args, exc_info=(type(exc), exc, exc.__traceback__))
    else:
        logger.warning(message, *args)


def _format_validation_message(errors: list[dict[str, Any]]) -> str:
    messages: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.get("loc", []))
        message = error.get("msg", "Invalid request.")
        if location:
            messages.append(f"{location}: {message}")
        else:
            messages.append(message)
    return "; ".join(messages) or "Invalid request."
