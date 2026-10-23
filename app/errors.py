"""Domain exceptions mapped to a consistent error envelope."""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class LedgerError(Exception):
    """Base for domain-level errors."""


class NotFoundError(LedgerError):
    pass


class InsufficientFundsError(LedgerError):
    pass


class IdempotencyConflictError(LedgerError):
    pass


class ForbiddenError(LedgerError):
    pass


def error_envelope(code: int, message: str, request_id: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


async def ledger_error_handler(request: Request, exc: LedgerError) -> JSONResponse:
    request_id = getattr(request, "state", None) and getattr(request.state, "request_id", None) or ""
    if isinstance(exc, NotFoundError):
        return JSONResponse(status_code=404, content=error_envelope(404, str(exc), request_id))
    if isinstance(exc, InsufficientFundsError):
        return JSONResponse(status_code=422, content=error_envelope("INSUFFICIENT_FUNDS", str(exc), request_id))
    if isinstance(exc, IdempotencyConflictError):
        return JSONResponse(status_code=409, content=error_envelope("IDEMPOTENCY_CONFLICT", str(exc), request_id))
    if isinstance(exc, ForbiddenError):
        return JSONResponse(status_code=403, content=error_envelope("FORBIDDEN", str(exc), request_id))
    return JSONResponse(status_code=500, content=error_envelope(500, str(exc), request_id))


async def generic_http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request, "state", None) and getattr(request.state, "request_id", None) or ""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(exc.status_code, exc.detail, request_id),
    )
