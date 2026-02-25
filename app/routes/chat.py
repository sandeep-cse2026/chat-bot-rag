"""Chat blueprint — main user-facing routes.

Routes:
    GET  /          → Render the chat UI
    POST /chat      → Process a chat message
    POST /chat/clear → Clear a session's history
"""
from __future__ import annotations

import uuid

import structlog
from flask import Blueprint, current_app, jsonify, render_template, request
from pydantic import ValidationError

from app.models.requests import ChatRequest
from app.utils.sanitizer import sanitize_user_input

logger = structlog.get_logger(__name__)

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/")
def index():
    """Render the chat UI."""
    return render_template("index.html")


@chat_bp.route("/chat", methods=["POST"])
def chat():
    """Process a chat message and return the assistant's response.

    Request JSON:
        {
            "message": "Tell me about Naruto",
            "session_id": "abc-123"   // optional
        }

    Response JSON:
        {
            "success": true,
            "response": "Naruto is a popular anime...",
            "session_id": "abc-123"
        }
    """
    # Parse and validate request
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({
            "success": False,
            "error": {"message": "Invalid JSON body", "code": 400},
        }), 400

    try:
        req = ChatRequest(**data)
    except ValidationError as e:
        errors = e.errors()
        message = errors[0].get("msg", "Validation error") if errors else "Invalid request"
        return jsonify({
            "success": False,
            "error": {"message": message, "code": 422},
        }), 422

    # Sanitize user input
    try:
        clean_message = sanitize_user_input(req.message)
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": {"message": str(e), "code": 422},
        }), 422

    # Get or generate session ID
    session_id = req.session_id or str(uuid.uuid4())

    # Process through orchestrator
    orchestrator = current_app.config["ORCHESTRATOR"]
    try:
        response_text = orchestrator.process_message(session_id, clean_message)
    except Exception as e:
        logger.error("chat_processing_error", error=str(e), exc_info=True)
        return jsonify({
            "success": False,
            "error": {"message": "Failed to process your message. Please try again.", "code": 500},
        }), 500

    return jsonify({
        "success": True,
        "response": response_text,
        "session_id": session_id,
    })


@chat_bp.route("/chat/clear", methods=["POST"])
def clear_chat():
    """Clear a session's conversation history.

    Request JSON:
        { "session_id": "abc-123" }

    Response JSON:
        { "success": true, "message": "Session cleared" }
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"success": False, "error": {"message": "Invalid JSON", "code": 400}}), 400

    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"success": False, "error": {"message": "session_id required", "code": 422}}), 422

    orchestrator = current_app.config["ORCHESTRATOR"]
    orchestrator.clear_session(session_id)

    return jsonify({"success": True, "message": "Session cleared"})
