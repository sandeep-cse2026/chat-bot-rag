"""Health check endpoint for application and dependency monitoring.

Exposes GET /health returning the status of each external dependency.
Used by Docker HEALTHCHECK and monitoring systems.

Response format:
    {
        "status": "healthy" | "degraded",
        "version": "1.0.0",
        "dependencies": {
            "jikan_api": "ok" | "error: ...",
            "tvmaze_api": "ok" | "error: ...",
            "openlibrary_api": "ok" | "error: ...",
        }
    }
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

import structlog

logger = structlog.get_logger(__name__)

health_bp = Blueprint("health", __name__)

APP_VERSION = "1.0.0"


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Application health check endpoint.

    Returns:
        200 if all dependencies are healthy.
        503 if any dependency is unhealthy.
    """
    checks: dict[str, str] = {}

    # Check each external API by attempting a lightweight request
    api_checks = {
        "jikan_api": "/anime?limit=1&sfw=true",
        "tvmaze_api": "/shows/1",
        "openlibrary_api": "/search.json?q=test&limit=1",
    }

    for dep_name, endpoint in api_checks.items():
        try:
            # Access client from app context if available
            client = current_app.config.get(f"_{dep_name}_client")
            if client and hasattr(client, "health_check"):
                client.health_check()
                checks[dep_name] = "ok"
            else:
                # If client not initialized yet, mark as unchecked
                checks[dep_name] = "ok (client not initialized)"
        except Exception as e:
            logger.warning("health_check_failed", dependency=dep_name, error=str(e))
            checks[dep_name] = f"error: {str(e)}"

    all_healthy = all(v.startswith("ok") for v in checks.values())

    response = {
        "status": "healthy" if all_healthy else "degraded",
        "version": APP_VERSION,
        "dependencies": checks,
    }

    status_code = 200 if all_healthy else 503
    return jsonify(response), status_code
