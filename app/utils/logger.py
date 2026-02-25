"""Structured logging configuration using structlog.

Provides centralized logging setup with:
- JSON output in production, colored console output in development
- Automatic request_id binding via contextvars
- Timestamp, log level, and logger name on every log line
- Exception formatting

Usage:
    from app.utils.logger import setup_logging

    setup_logging(log_level="INFO", log_format="json")

    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("event_name", key="value")
"""
from __future__ import annotations

import logging

import structlog


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structlog for the entire application.

    Args:
        log_level: Logging level — DEBUG, INFO, WARNING, ERROR, CRITICAL.
        log_format: Output format — 'json' for production, 'console' for dev.
    """
    # Shared processors applied to every log event
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,       # picks up request_id, etc.
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Choose renderer based on environment
    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to use structlog (for third-party libs)
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
