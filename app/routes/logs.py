"""Logs route — API endpoints for viewing conversation logs.

Provides read-only access to conversation log files for debugging,
auditing, and observability.

Endpoints:
    GET /logs          → List all session summaries
    GET /logs/<id>     → Full log for a specific session
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/logs", methods=["GET"])
def list_logs():
    """List all conversation log sessions with summaries.

    Returns:
        JSON array of session summaries.
    """
    conv_logger = current_app.config.get("CONVERSATION_LOGGER")
    if not conv_logger:
        return jsonify({"error": "Conversation logging is disabled"}), 503

    sessions = conv_logger.list_sessions()
    return jsonify({"sessions": sessions, "count": len(sessions)})


@logs_bp.route("/logs/<session_id>", methods=["GET"])
def get_log(session_id):
    """Get the full conversation log for a specific session.

    Args:
        session_id: Session identifier from the URL.

    Returns:
        Full session log JSON, or 404 if not found.
    """
    conv_logger = current_app.config.get("CONVERSATION_LOGGER")
    if not conv_logger:
        return jsonify({"error": "Conversation logging is disabled"}), 503

    log_data = conv_logger.get_session_log(session_id)
    if log_data is None:
        return jsonify({"error": f"No log found for session '{session_id}'"}), 404

    return jsonify(log_data)
