import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security import sanitize_log_path

logger = structlog.get_logger(__name__)


class StructlogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()),
            path=sanitize_log_path(request.url.path),
            method=request.method,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error("Unhandled exception", exc_info=True)
            raise
        elapsed = time.perf_counter() - start
        logger.info(
            "Request completed",
            status_code=response.status_code,
            elapsed=round(elapsed, 4),
        )
        return response
