"""Request ID middleware for log correlation.

Injects a unique X-Request-ID into every incoming request, enabling
log correlation across the full request lifecycle. If the client sends
an X-Request-ID header, it is reused; otherwise a new UUID is generated.

Usage:
    from app.middleware.request_id import init_request_id_middleware
    init_request_id_middleware(app)
"""
from __future__ import annotations

import uuid

import structlog
from flask import Flask, g, request


def init_request_id_middleware(app: Flask) -> None:
    """Register before/after hooks for request ID tracing.

    Args:
        app: Flask application instance.
    """
    logger = structlog.get_logger(__name__)

    @app.before_request
    def inject_request_id() -> None:
        """Inject request ID into Flask's g object and structlog context."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        g.request_id = request_id

        # Bind request_id to structlog context for all logs in this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.path,
        )

        logger.debug("request_started")

    @app.after_request
    def attach_request_id(response):
        """Attach request ID to response headers and log completion."""
        request_id = g.get("request_id", "unknown")
        response.headers["X-Request-ID"] = request_id

        logger.debug(
            "request_completed",
            status=response.status_code,
        )
        return response
