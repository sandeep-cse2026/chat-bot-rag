"""Chat orchestrator — the central brain tying LLM + API clients together.

Manages the full conversation loop:
    User message → LLM (with tools) → Tool execution → LLM (with results) → Response

Handles multi-turn tool calling (up to MAX_TOOL_ITERATIONS) and
session-based conversation history with automatic cleanup.

Usage:
    orchestrator = ChatOrchestrator(llm_service, tool_router, settings)
    response = orchestrator.process_message("session_123", "Tell me about Naruto")
"""
from __future__ import annotations

import threading
import time
from typing import Any

import structlog

from app.config import Settings
from app.prompts.templates import SYSTEM_PROMPT, get_tools
from app.services.llm_service import ConversationHistory, LLMService
from app.services.tool_router import ToolRouter
from app.utils.exceptions import ChatBotError, ToolExecutionError

logger = structlog.get_logger(__name__)

# Maximum rounds of tool calling before forcing a text response
MAX_TOOL_ITERATIONS = 3


class ChatOrchestrator:
    """Main orchestration service for the chatbot.

    Manages the conversation loop between user → LLM → tools → LLM → response.
    Maintains per-session conversation histories and handles tool execution.

    Args:
        llm_service: LLMService instance for OpenRouter communication.
        tool_router: ToolRouter instance for function execution.
        settings: Application settings.
    """

    def __init__(
        self,
        llm_service: LLMService,
        tool_router: ToolRouter,
        settings: Settings,
    ) -> None:
        self._llm = llm_service
        self._router = tool_router
        self._settings = settings

        # Session management
        self._sessions: dict[str, ConversationHistory] = {}
        self._session_timestamps: dict[str, float] = {}
        self._lock = threading.Lock()

        # Tool definitions (cached)
        self._tools = get_tools()

    # ── Public API ────────────────────────────────────────────────────

    def process_message(self, session_id: str, user_message: str) -> str:
        """Process a user message and return the assistant's response.

        This is the main entry point. It:
        1. Gets or creates a conversation history for the session
        2. Adds the user message
        3. Sends to the LLM with tool definitions
        4. If the LLM returns tool calls, executes them and loops back
        5. Returns the final text response

        Args:
            session_id: Unique session identifier.
            user_message: The user's message text.

        Returns:
            The assistant's final text response.

        Raises:
            ChatBotError: On LLM or tool execution failure.
        """
        history = self._get_or_create_session(session_id)
        history.add_user_message(user_message)

        logger.info(
            "processing_message",
            session_id=session_id,
            message_length=len(user_message),
            history_length=len(history.messages),
        )

        try:
            response_text = self._run_conversation_loop(history)

            # Add the final response to history
            history.add_assistant_message(response_text)

            logger.info(
                "message_processed",
                session_id=session_id,
                response_length=len(response_text),
            )

            return response_text

        except Exception as e:
            logger.error(
                "message_processing_failed",
                session_id=session_id,
                error=str(e),
                exc_info=True,
            )
            raise

    def get_session_count(self) -> int:
        """Return the number of active sessions."""
        return len(self._sessions)

    def clear_session(self, session_id: str) -> bool:
        """Clear a specific session's history.

        Args:
            session_id: Session to clear.

        Returns:
            True if the session existed and was cleared.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._session_timestamps.pop(session_id, None)
                logger.info("session_cleared", session_id=session_id)
                return True
            return False

    def cleanup_expired_sessions(self) -> int:
        """Remove sessions that have been idle longer than SESSION_TTL_SECONDS.

        Returns:
            Number of sessions cleaned up.
        """
        ttl = self._settings.SESSION_TTL_SECONDS
        now = time.monotonic()
        expired = []

        with self._lock:
            for sid, last_active in self._session_timestamps.items():
                if now - last_active > ttl:
                    expired.append(sid)

            for sid in expired:
                del self._sessions[sid]
                del self._session_timestamps[sid]

        if expired:
            logger.info("sessions_cleaned_up", count=len(expired))

        return len(expired)

    # ── Core Loop ─────────────────────────────────────────────────────

    def _run_conversation_loop(self, history: ConversationHistory) -> str:
        """Run the LLM conversation loop with tool calling.

        Sends the conversation to the LLM. If the LLM responds with
        tool calls, executes them, appends results, and sends back to
        the LLM. Repeats up to MAX_TOOL_ITERATIONS times.

        Args:
            history: The conversation history for this session.

        Returns:
            The final text response from the LLM.
        """
        for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
            # Send to LLM
            llm_response = self._llm.chat_completion(
                messages=history.messages,
                tools=self._tools,
            )

            # If the LLM returned a text response, we're done
            if not llm_response.has_tool_calls:
                return llm_response.content or "I couldn't generate a response. Please try again."

            # LLM wants to call tools
            logger.info(
                "tool_calls_received",
                iteration=iteration,
                tool_count=len(llm_response.tool_calls),
                tools=[tc.name for tc in llm_response.tool_calls],
            )

            # Add the assistant's tool call message to history
            history.add_assistant_tool_calls(llm_response.tool_calls)

            # Execute each tool call and add results
            for tool_call in llm_response.tool_calls:
                result = self._execute_tool_call(tool_call.name, tool_call.arguments)
                history.add_tool_result(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    result=result,
                )

        # If we've exhausted iterations, ask the LLM for a final answer
        # without tools to force a text response
        logger.warning(
            "max_tool_iterations_reached",
            iterations=MAX_TOOL_ITERATIONS,
        )
        final_response = self._llm.chat_completion(
            messages=history.messages,
            tools=None,  # No tools — force text response
        )
        return final_response.content or "I gathered some data but couldn't formulate a response. Please try again."

    def _execute_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a single tool call and return the result.

        Wraps the ToolRouter.execute() call with error handling,
        returning a structured error message on failure instead of
        crashing the conversation loop.

        Args:
            tool_name: Function name from the LLM.
            arguments: Arguments dict from the LLM.

        Returns:
            JSON string result (success or error message).
        """
        try:
            return self._router.execute(tool_name, arguments)
        except ToolExecutionError as e:
            logger.warning("tool_call_failed", tool=tool_name, error=str(e))
            return f'{{"error": "Tool \'{tool_name}\' failed: {e.message}"}}'
        except Exception as e:
            logger.error(
                "tool_call_unexpected_error",
                tool=tool_name,
                error=str(e),
                exc_info=True,
            )
            return f'{{"error": "An unexpected error occurred while executing \'{tool_name}\'"}}'

    # ── Session Management ────────────────────────────────────────────

    def _get_or_create_session(self, session_id: str) -> ConversationHistory:
        """Get an existing session or create a new one.

        Args:
            session_id: Unique session identifier.

        Returns:
            ConversationHistory for the session.
        """
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = ConversationHistory(
                    max_length=self._settings.MAX_CONVERSATION_HISTORY,
                    system_prompt=SYSTEM_PROMPT,
                )
                logger.info("session_created", session_id=session_id)

            self._session_timestamps[session_id] = time.monotonic()
            return self._sessions[session_id]
