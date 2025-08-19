from __future__ import annotations

import logging
from contextvars import ContextVar


# Context variable that holds the current request id
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Logging filter to inject the request id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = request_id_ctx_var.get()
        return True
