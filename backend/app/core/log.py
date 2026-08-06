"""Central logging configuration — single-line JSON records for operational visibility.

Every log line is a JSON object (ts/level/logger/request_id/msg, plus `exc` when a
traceback is attached) so the stream can be tailed, grapped and shipped as-is.
`setup_logging()` is idempotent and called once at import; `install_middleware()`
attaches a per-request `request_id` that correlates access and exception records,
and `install_exception_handlers()` guarantees no unhandled error is silent.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

LOG_LEVEL = "INFO"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"

logger = logging.getLogger("earthpulse")


def request_id() -> str:
    """Correlation id for the current request (a no-op `-` outside a request)."""
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Structure log records as a single JSON line; never spans newlines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, _DATE_FMT),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", None) or request_id(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = LOG_LEVEL) -> None:
    """Install the JSON console handler once; quiet noisy third-party loggers."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not any(isinstance(h, logging.StreamHandler) and getattr(h, "_em_json", False)
               for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler._em_json = True
        root.addHandler(handler)
    for noisy in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine", "watchfiles.main"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def install_middleware(app: FastAPI) -> None:
    """Request + response access log with a unique request_id per call."""

    @app.middleware("http")
    async def _request_log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = uuid4().hex[:12]
        token = _request_id.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            logger.error("request failed", exc_info=True, extra={
                "request_id": rid, "method": request.method, "path": request.url.path,
                "client": request.client.host if request.client else "-",
            })
            raise
        finally:
            _request_id.reset(token)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            level = logging.INFO if status < 500 else logging.WARNING
            logger.log(level, "request completed", extra={
                "request_id": rid, "method": request.method, "path": request.url.path,
                "status": status, "duration_ms": round(elapsed_ms, 1),
            })


def install_exception_handlers(app: FastAPI) -> None:
    """Final trap: never return a silent 500. Log full stack first, then a JSON error."""

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error", exc_info=exc, extra={
            "request_id": request_id(), "method": request.method, "path": request.url.path,
        })
        return JSONResponse(status_code=500, content={"detail": "internal server error"})