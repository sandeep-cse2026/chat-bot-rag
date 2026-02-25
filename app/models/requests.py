"""Pydantic models for API request validation."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Incoming chat message request.

    Attributes:
        message: The user's message text (1-2000 chars).
        session_id: Optional session ID for conversation continuity.
    """
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: str = Field(default="", description="Session ID for conversation continuity")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v
