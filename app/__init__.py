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

from app.config import get_settings, Settings
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
    - Service initialization (API clients, LLM, orchestrator)
    - Startup validation
    - Blueprint registration (health, chat)

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
        r"/chat/*": {"origins": "*"},
        r"/health": {"origins": "*"},
    })

    # ── Services ──────────────────────────────────────────────────────
    _init_services(app, settings)

    # ── Startup validation ────────────────────────────────────────────
    _validate_startup(settings, logger)

    # ── Blueprints ────────────────────────────────────────────────────
    from app.routes.health import health_bp
    from app.routes.chat import chat_bp
    from app.routes.logs import logs_bp
    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(logs_bp)

    logger.info(
        "app_started",
        env=settings.FLASK_ENV,
        model=settings.OPENROUTER_MODEL,
        log_level=settings.LOG_LEVEL,
    )

    return app


def _init_services(app: Flask, settings: Settings) -> None:
    """Initialize API clients, LLM service, and chat orchestrator.

    All services are stored on `app.config` for access via `current_app`.

    Args:
        app: Flask application instance.
        settings: Application settings.
    """
    from app.api_clients.jikan_client import JikanClient
    from app.api_clients.tvmaze_client import TVMazeClient
    from app.api_clients.openlibrary_client import OpenLibraryClient
    from app.services.llm_service import LLMService
    from app.services.tool_router import ToolRouter
    from app.services.chat_orchestrator import ChatOrchestrator
    from app.services.conversation_logger import ConversationLogger
    from app.services.context_service import ContextService

    logger = structlog.get_logger(__name__)
    logger.info("initializing_services")

    # API Clients
    jikan = JikanClient(
        base_url=settings.JIKAN_BASE_URL,
        rate_limit=settings.JIKAN_RATE_LIMIT,
        timeout=settings.HTTP_TIMEOUT,
        max_retries=settings.HTTP_MAX_RETRIES,
        cache_ttl=settings.CACHE_TTL_SECONDS,
        cache_max_size=settings.CACHE_MAX_SIZE,
    )
    tvmaze = TVMazeClient(
        base_url=settings.TVMAZE_BASE_URL,
        rate_limit=settings.TVMAZE_RATE_LIMIT,
        timeout=settings.HTTP_TIMEOUT,
        max_retries=settings.HTTP_MAX_RETRIES,
        cache_ttl=settings.CACHE_TTL_SECONDS,
        cache_max_size=settings.CACHE_MAX_SIZE,
    )
    openlibrary = OpenLibraryClient(
        base_url=settings.OPENLIBRARY_BASE_URL,
        rate_limit=settings.OPENLIBRARY_RATE_LIMIT,
        timeout=settings.HTTP_TIMEOUT,
        max_retries=settings.HTTP_MAX_RETRIES,
        cache_ttl=settings.CACHE_TTL_SECONDS,
        cache_max_size=settings.CACHE_MAX_SIZE,
    )

    # LLM Service
    llm_service = LLMService(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        base_url=settings.OPENROUTER_BASE_URL,
    )

    # Tool Router
    tool_router = ToolRouter(jikan, tvmaze, openlibrary)

    # Conversation Logger (optional)
    conv_logger = None
    if settings.CONVERSATION_LOG_ENABLED:
        conv_logger = ConversationLogger(log_dir=settings.CONVERSATION_LOG_DIR)

    # Context Service (ChromaDB vector DB)
    context_service = ContextService(
        persist_dir=settings.CHROMA_PERSIST_DIR,
        collection_name=settings.CHROMA_COLLECTION_NAME,
        max_results=settings.CONTEXT_MAX_RESULTS,
        similarity_threshold=settings.CONTEXT_SIMILARITY_THRESHOLD,
    )

    # Chat Orchestrator
    orchestrator = ChatOrchestrator(
        llm_service, tool_router, settings,
        conversation_logger=conv_logger,
        context_service=context_service,
    )

    # Store on app config for access via current_app
    app.config["ORCHESTRATOR"] = orchestrator
    app.config["LLM_SERVICE"] = llm_service
    app.config["JIKAN_CLIENT"] = jikan
    app.config["TVMAZE_CLIENT"] = tvmaze
    app.config["OPENLIBRARY_CLIENT"] = openlibrary
    app.config["CONVERSATION_LOGGER"] = conv_logger
    app.config["CONTEXT_SERVICE"] = context_service

    logger.info("services_initialized")


def _validate_startup(settings: Settings, logger) -> None:
    """Run startup validation — fail fast if critical dependencies are missing.

    Checks external API reachability (warnings only, non-blocking).

    Args:
        settings: Application settings instance.
        logger: Structlog logger instance.
    """
    logger.info("startup_validation", phase="begin")

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
