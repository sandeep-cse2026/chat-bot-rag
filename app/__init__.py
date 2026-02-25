"""Entertainment & Books RAG Chatbot — Flask Application Package.

This is the main application package. The `create_app()` factory function
initializes the Flask application with all configurations, middleware,
services, and blueprints.
"""
from __future__ import annotations

import httpx
import structlog
from flask import Flask
from flask_cors import CORS

from app.config import get_settings
from app.utils.logger import setup_logging
from app.middleware.request_id import init_request_id_middleware
from app.middleware.error_handlers import register_error_handlers


def create_app() -> Flask:
    """Application factory pattern.

    Creates and configures the Flask application with:
    - Pydantic-based configuration loading
    - Structured logging (structlog)
    - Request ID middleware
    - Global error handlers
    - CORS configuration
    - Startup validation
    - Blueprint registration (health)

    Returns:
        Configured Flask application instance.
    """
    # Load validated config
    settings = get_settings()

    # ── Logging (must be first so all subsequent logs are formatted) ──
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger = structlog.get_logger(__name__)

    # ── Flask app ─────────────────────────────────────────────────────
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["FLASK_DEBUG"] = settings.FLASK_DEBUG

    # Store settings on app for access in blueprints
    app.config["SETTINGS"] = settings

    # ── Middleware ─────────────────────────────────────────────────────
    init_request_id_middleware(app)
    register_error_handlers(app)

    # ── CORS ──────────────────────────────────────────────────────────
    CORS(app, resources={
        r"/chat": {"origins": "*"},
        r"/health": {"origins": "*"},
    })

    # ── Startup validation ────────────────────────────────────────────
    _validate_startup(settings, logger)

    # ── Blueprints ────────────────────────────────────────────────────
    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

    # Note: chat_bp will be registered in Phase 6

    logger.info(
        "app_started",
        env=settings.FLASK_ENV,
        model=settings.OPENROUTER_MODEL,
        log_level=settings.LOG_LEVEL,
    )

    return app


def _validate_startup(settings, logger) -> None:
    """Run startup validation — fail fast if critical dependencies are missing.

    Checks:
    1. OpenRouter API key is set (already validated by Pydantic)
    2. External APIs are reachable (warnings only, non-blocking)

    Args:
        settings: Application settings instance.
        logger: Structlog logger instance.
    """
    logger.info("startup_validation", phase="begin")

    # External API reachability (non-blocking — only log warnings)
    api_checks = [
        ("Jikan", settings.JIKAN_BASE_URL),
        ("TVMaze", f"{settings.TVMAZE_BASE_URL}/shows/1"),
        ("OpenLibrary", f"{settings.OPENLIBRARY_BASE_URL}/search.json?q=test&limit=1"),
    ]

    for name, url in api_checks:
        try:
            resp = httpx.get(url, timeout=10)
            logger.info("startup_check", api=name, status=resp.status_code)
        except Exception as e:
            logger.warning("startup_check_failed", api=name, error=str(e))

    logger.info("startup_validation", phase="complete")
