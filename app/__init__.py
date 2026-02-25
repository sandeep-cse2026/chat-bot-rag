"""Entertainment & Books RAG Chatbot — Flask Application Package.

This is the main application package. The `create_app()` factory function
initializes the Flask application with all configurations, middleware,
services, and blueprints.
"""
from flask import Flask


def create_app() -> Flask:
    """Application factory pattern.

    Creates and configures the Flask application with:
    - Pydantic-based configuration loading
    - Structured logging (structlog)
    - Request ID middleware
    - Global error handlers
    - CORS configuration
    - API clients and LLM service initialization
    - Startup validation
    - Blueprint registration (chat, health)

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # ── Placeholder: Full wiring happens in Phase 2 → Phase 6 ──
    # This factory will be expanded as each phase is implemented.

    return app
