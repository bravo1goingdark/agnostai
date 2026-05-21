import logging
import sys
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def configure_logging(log_level: str) -> None:
    root_logger = logging.getLogger()
    logging.basicConfig(
        level=log_level.upper(),
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s request_id=%(request_id)s %(message)s"
        ),
        stream=sys.stdout,
        force=True,
    )
    root_logger.addFilter(RequestIdFilter())


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured access log line per HTTP request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        start = perf_counter()
        logger = logging.getLogger("app.request")

        try:
            response: Response = await call_next(request)
        except Exception:
            elapsed_ms = int((perf_counter() - start) * 1000)
            logger.exception(
                "request_failed method=%s path=%s elapsed_ms=%s",
                request.method,
                request.url.path,
                elapsed_ms,
                extra={"request_id": request_id},
            )
            raise

        elapsed_ms = int((perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete method=%s path=%s status_code=%s elapsed_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={"request_id": request_id},
        )
        return response
