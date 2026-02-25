"""Pydantic models for API response serialization."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatResponse(BaseModel):
    """Outgoing chat response.

    Attributes:
        success: Whether the request was processed successfully.
        response: The assistant's response text.
        session_id: Session ID for conversation continuity.
    """
    success: bool = True
    response: str = Field(..., description="Assistant response text")
    session_id: str = Field(..., description="Session ID")


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: dict = Field(..., description="Error details with 'message' and 'code'")
