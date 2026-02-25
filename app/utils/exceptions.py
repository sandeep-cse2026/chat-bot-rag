"""Custom exception hierarchy for the chatbot application.

All application-specific exceptions inherit from ChatBotError,
enabling uniform error handling in the global error handlers.

Hierarchy:
    ChatBotError (base)
    ├── APIClientError          — External API failures (Jikan, TVMaze, OpenLibrary)
    │   ├── APIRateLimitError   — 429 Too Many Requests
    │   └── APITimeoutError     — Request timeout
    ├── LLMServiceError         — OpenRouter / LLM failures
    │   └── LLMRateLimitError   — OpenRouter rate limit
    ├── ToolExecutionError      — Tool router execution failures
    └── ValidationError         — Input validation failures
"""
from __future__ import annotations


class ChatBotError(Exception):
    """Base exception for the chatbot application."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ── API Client Errors ─────────────────────────────────────────────────

class APIClientError(ChatBotError):
    """Raised when an external API call fails."""

    def __init__(
        self,
        message: str,
        client_name: str = "unknown",
        status_code: int = 502,
        upstream_status: int | None = None,
    ) -> None:
        self.client_name = client_name
        self.upstream_status = upstream_status
        super().__init__(message, status_code)


class APIRateLimitError(APIClientError):
    """Raised when an external API returns 429 Too Many Requests."""

    def __init__(self, client_name: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(
            message=f"{client_name} API rate limit exceeded. Try again shortly.",
            client_name=client_name,
            status_code=429,
            upstream_status=429,
        )


class APITimeoutError(APIClientError):
    """Raised when an external API request times out."""

    def __init__(self, client_name: str, timeout: float) -> None:
        super().__init__(
            message=f"{client_name} API request timed out after {timeout}s.",
            client_name=client_name,
            status_code=504,
        )


# ── LLM Service Errors ───────────────────────────────────────────────

class LLMServiceError(ChatBotError):
    """Raised when the LLM service (OpenRouter) fails."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message, status_code)


class LLMRateLimitError(LLMServiceError):
    """Raised when OpenRouter returns 429."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(
            message="LLM rate limit exceeded. Please wait and try again.",
            status_code=429,
        )


# ── Tool Execution Errors ────────────────────────────────────────────

class ToolExecutionError(ChatBotError):
    """Raised when a tool/function call fails during orchestration."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(
            message=f"Tool '{tool_name}' failed: {message}",
            status_code=500,
        )


# ── Validation Errors ────────────────────────────────────────────────

class InputValidationError(ChatBotError):
    """Raised when user input fails validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)
