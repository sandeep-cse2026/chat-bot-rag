"""Global Flask error handlers for consistent JSON error responses.

Registers handlers for standard HTTP errors and custom ChatBotError
exceptions, ensuring the API always returns:
    { "success": false, "error": { "message": "...", "code": <int> } }

Usage:
    from app.middleware.error_handlers import register_error_handlers
    register_error_handlers(app)
"""
from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

import structlog

from app.utils.exceptions import ChatBotError

logger = structlog.get_logger(__name__)


def _error_response(message: str, code: int):
    """Create a standardized JSON error response.

    Args:
        message: Human-readable error message.
        code: HTTP status code.

    Returns:
        Tuple of (response, status_code).
    """
    return jsonify({
        "success": False,
        "error": {
            "message": message,
            "code": code,
        },
    }), code


def register_error_handlers(app: Flask) -> None:
    """Register global error handlers on the Flask app.

    Args:
        app: Flask application instance.
    """

    # ── Standard HTTP Errors ──────────────────────────────────────────

    @app.errorhandler(400)
    def bad_request(e):
        return _error_response("Bad request", 400)

    @app.errorhandler(404)
    def not_found(e):
        return _error_response("Not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return _error_response("Method not allowed", 405)

    @app.errorhandler(422)
    def unprocessable_entity(e):
        message = str(e.description) if hasattr(e, "description") else str(e)
        return _error_response(message, 422)

    @app.errorhandler(429)
    def rate_limited(e):
        return _error_response("Too many requests. Please slow down.", 429)

    @app.errorhandler(500)
    def internal_error(e):
        logger.error("unhandled_server_error", error=str(e), exc_info=True)
        return _error_response("Internal server error", 500)

    # ── Custom Application Errors ─────────────────────────────────────

    @app.errorhandler(ChatBotError)
    def handle_chatbot_error(e: ChatBotError):
        """Handle all custom ChatBotError exceptions."""
        logger.warning(
            "chatbot_error",
            error=e.message,
            error_type=type(e).__name__,
            status_code=e.status_code,
        )
        return _error_response(e.message, e.status_code)

    # ── Catch-all for unexpected Werkzeug HTTP exceptions ─────────────

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        """Catch any HTTPException not explicitly handled above."""
        return _error_response(e.description or "Unknown error", e.code or 500)

    # ── Catch-all for truly unhandled exceptions ──────────────────────

    @app.errorhandler(Exception)
    def handle_unexpected_error(e: Exception):
        """Last resort handler for unhandled exceptions."""
        logger.error(
            "unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return _error_response("An unexpected error occurred", 500)
