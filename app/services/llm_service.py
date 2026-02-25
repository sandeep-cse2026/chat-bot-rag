"""OpenRouter LLM service for chat completions with function calling.

Handles all communication with the OpenRouter API, which provides an
OpenAI-compatible chat completions endpoint. Supports:
- Chat completions with tool/function definitions
- Function call parsing and extraction
- Conversation history management with configurable max length
- Structured logging of all LLM interactions

Usage:
    from app.services.llm_service import LLMService

    service = LLMService(api_key="...", model="google/gemini-2.0-flash-001")
    response = service.chat_completion(messages, tools)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.utils.exceptions import LLMRateLimitError, LLMServiceError

logger = structlog.get_logger(__name__)


@dataclass
class ToolCall:
    """Parsed tool/function call from the LLM response."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Structured response from the LLM.

    Either `content` is populated (text response) or `tool_calls` is
    populated (function calling), but not both.
    """
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """Whether the response contains function calls."""
        return bool(self.tool_calls)


class LLMService:
    """Service for interacting with OpenRouter's chat completions API.

    Manages HTTP communication with OpenRouter, parses responses
    (including tool/function calls), and provides conversation history
    management.

    Args:
        api_key: OpenRouter API key.
        model: LLM model identifier (e.g., "google/gemini-2.0-flash-001").
        base_url: OpenRouter API base URL.
        timeout: HTTP request timeout in seconds.
        max_retries: Max retry attempts for failed requests.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-2.0-flash-001",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 60,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries

        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout, connect=10),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://chatbot-rag.local",
                "X-Title": "Entertainment & Books RAG Chatbot",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Core API ──────────────────────────────────────────────────────

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter.

        Args:
            messages: Conversation messages in OpenAI format.
            tools: Tool/function definitions (optional).
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            Parsed LLMResponse with content and/or tool calls.

        Raises:
            LLMServiceError: On non-retryable API failures.
            LLMRateLimitError: When rate limited after retries.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        return self._send_request(payload)

    # ── Request Handling ──────────────────────────────────────────────

    def _send_request(self, payload: dict[str, Any]) -> LLMResponse:
        """Send request to OpenRouter with retry logic.

        Args:
            payload: Request body.

        Returns:
            Parsed LLMResponse.
        """
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "llm_request",
                    model=self._model,
                    messages_count=len(payload.get("messages", [])),
                    has_tools=bool(payload.get("tools")),
                    attempt=attempt,
                )

                start = time.monotonic()
                response = self._client.post("/chat/completions", json=payload)
                duration_ms = round((time.monotonic() - start) * 1000)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 5))
                    if attempt < self._max_retries:
                        logger.warning(
                            "llm_rate_limited",
                            retry_after=retry_after,
                            attempt=attempt,
                        )
                        time.sleep(retry_after)
                        continue
                    raise LLMRateLimitError(retry_after=retry_after)

                # Handle other errors
                if response.status_code >= 400:
                    error_body = response.text
                    logger.error(
                        "llm_error",
                        status=response.status_code,
                        body=error_body[:500],
                        attempt=attempt,
                    )
                    if attempt < self._max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    raise LLMServiceError(
                        message=f"OpenRouter API error: {response.status_code} — {error_body[:200]}",
                        status_code=response.status_code,
                    )

                # Parse successful response
                data = response.json()
                result = self._parse_response(data)

                logger.info(
                    "llm_response",
                    model=result.model,
                    has_content=bool(result.content),
                    tool_calls_count=len(result.tool_calls),
                    finish_reason=result.finish_reason,
                    duration_ms=duration_ms,
                    usage=result.usage,
                )

                return result

            except (LLMServiceError, LLMRateLimitError):
                raise
            except httpx.TimeoutException as e:
                logger.warning("llm_timeout", attempt=attempt, error=str(e))
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMServiceError(
                    message="OpenRouter request timed out",
                    status_code=504,
                ) from e
            except Exception as e:
                logger.error("llm_unexpected_error", error=str(e), exc_info=True)
                raise LLMServiceError(
                    message=f"Unexpected LLM error: {str(e)}",
                ) from e

        # Should not reach here, but safety net
        raise LLMServiceError(message="All LLM retries exhausted")

    # ── Response Parsing ──────────────────────────────────────────────

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse the raw OpenRouter JSON response into an LLMResponse.

        Args:
            data: Raw JSON response from OpenRouter.

        Returns:
            Structured LLMResponse.
        """
        choices = data.get("choices", [])
        if not choices:
            raise LLMServiceError(
                message="OpenRouter returned no choices in response"
            )

        choice = choices[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "")

        # Parse usage
        usage = data.get("usage", {})
        usage_info = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        # Parse tool calls if present
        tool_calls: list[ToolCall] = []
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            try:
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")

                # Handle both string and dict arguments
                if isinstance(args_str, str):
                    arguments = json.loads(args_str)
                else:
                    arguments = args_str

                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=arguments,
                ))
            except json.JSONDecodeError as e:
                logger.warning(
                    "tool_call_parse_error",
                    tool_call=tc,
                    error=str(e),
                )
                continue

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            model=data.get("model", self._model),
            usage=usage_info,
            finish_reason=finish_reason,
        )


class ConversationHistory:
    """Manages conversation message history for a single session.

    Enforces maximum history length by trimming oldest messages
    (keeping the system prompt intact).

    Args:
        max_length: Maximum number of messages to retain.
        system_prompt: System prompt to always keep as the first message.
    """

    def __init__(self, max_length: int = 20, system_prompt: str = "") -> None:
        self._max_length = max_length
        self._messages: list[dict[str, Any]] = []

        if system_prompt:
            self._messages.append({
                "role": "system",
                "content": system_prompt,
            })

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Return the current message history."""
        return self._messages

    def add_user_message(self, content: str) -> None:
        """Add a user message to the history."""
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant text response to the history."""
        self._messages.append({"role": "assistant", "content": content})
        self._trim()

    def add_assistant_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        """Add an assistant message with tool calls to the history.

        Args:
            tool_calls: List of parsed ToolCall objects.
        """
        self._messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in tool_calls
            ],
        })
        self._trim()

    def add_tool_result(self, tool_call_id: str, name: str, result: str) -> None:
        """Add a tool/function result to the history.

        Args:
            tool_call_id: The tool call ID this result corresponds to.
            name: The tool/function name.
            result: The stringified tool result.
        """
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": result,
        })
        # Don't trim after tool results — they need to stay paired with tool_calls

    def clear(self) -> None:
        """Clear all messages except the system prompt."""
        system_msg = None
        if self._messages and self._messages[0].get("role") == "system":
            system_msg = self._messages[0]
        self._messages = [system_msg] if system_msg else []

    def _trim(self) -> None:
        """Trim messages to max_length, preserving system prompt and tool pairs.

        Strategy: Keep system prompt (position 0) + most recent messages.
        """
        if len(self._messages) <= self._max_length:
            return

        # Keep system prompt if present
        has_system = (
            self._messages and self._messages[0].get("role") == "system"
        )

        if has_system:
            system = self._messages[0]
            # Keep system + most recent messages
            keep_count = self._max_length - 1
            self._messages = [system] + self._messages[-keep_count:]
        else:
            self._messages = self._messages[-self._max_length:]
