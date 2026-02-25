"""Unit tests for the Chat Orchestrator."""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.llm_service import ConversationHistory, LLMResponse, LLMService, ToolCall
from app.services.tool_router import ToolRouter
from app.config import Settings


@pytest.fixture
def mock_llm():
    """Create a mock LLMService."""
    return MagicMock(spec=LLMService)


@pytest.fixture
def mock_router():
    """Create a mock ToolRouter."""
    return MagicMock(spec=ToolRouter)


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings(
        OPENROUTER_API_KEY="sk-or-v1-test-key-12345",
        SESSION_TTL_SECONDS=3600,
        MAX_CONVERSATION_HISTORY=20,
    )


@pytest.fixture
def orchestrator(mock_llm, mock_router, settings):
    """Create a ChatOrchestrator with mocks."""
    return ChatOrchestrator(mock_llm, mock_router, settings)


class TestProcessMessage:
    """Tests for ChatOrchestrator.process_message."""

    def test_simple_text_response(self, orchestrator, mock_llm):
        """LLM returns a text response (no tool calls)."""
        mock_llm.chat_completion.return_value = LLMResponse(
            content="Naruto is a popular anime!",
            finish_reason="stop",
        )

        result = orchestrator.process_message("session-1", "Tell me about Naruto")

        assert result == "Naruto is a popular anime!"
        assert mock_llm.chat_completion.call_count == 1

    def test_single_tool_call_then_response(self, orchestrator, mock_llm, mock_router):
        """LLM calls a tool, gets result, then responds with text."""
        # First call: LLM wants to use a tool
        tool_response = LLMResponse(
            tool_calls=[ToolCall(id="call_1", name="search_anime", arguments={"query": "Naruto"})],
            finish_reason="tool_calls",
        )
        # Second call: LLM responds with text after getting tool result
        text_response = LLMResponse(
            content="Naruto is a shonen anime about ninjas.",
            finish_reason="stop",
        )
        mock_llm.chat_completion.side_effect = [tool_response, text_response]
        mock_router.execute.return_value = '{"results": [{"title": "Naruto"}], "count": 1}'

        result = orchestrator.process_message("session-1", "Search for Naruto")

        assert result == "Naruto is a shonen anime about ninjas."
        assert mock_llm.chat_completion.call_count == 2
        mock_router.execute.assert_called_once_with("search_anime", {"query": "Naruto"})

    def test_multiple_tool_calls(self, orchestrator, mock_llm, mock_router):
        """LLM calls multiple tools in one response."""
        tool_response = LLMResponse(
            tool_calls=[
                ToolCall(id="call_1", name="search_anime", arguments={"query": "Naruto"}),
                ToolCall(id="call_2", name="search_manga", arguments={"query": "Naruto"}),
            ],
            finish_reason="tool_calls",
        )
        text_response = LLMResponse(
            content="Naruto has both anime and manga versions.",
            finish_reason="stop",
        )
        mock_llm.chat_completion.side_effect = [tool_response, text_response]
        mock_router.execute.return_value = '{"results": [], "count": 0}'

        result = orchestrator.process_message("session-1", "Compare Naruto anime and manga")

        assert result == "Naruto has both anime and manga versions."
        assert mock_router.execute.call_count == 2

    def test_tool_error_handled_gracefully(self, orchestrator, mock_llm, mock_router):
        """Tool execution error doesn't crash the loop."""
        tool_response = LLMResponse(
            tool_calls=[ToolCall(id="call_1", name="search_anime", arguments={"query": "test"})],
            finish_reason="tool_calls",
        )
        text_response = LLMResponse(
            content="I encountered an issue searching. Let me try differently.",
            finish_reason="stop",
        )
        mock_llm.chat_completion.side_effect = [tool_response, text_response]
        mock_router.execute.side_effect = Exception("API timeout")

        result = orchestrator.process_message("session-1", "Search for test")

        # Should still get a response — error is caught and sent back to LLM
        assert result == "I encountered an issue searching. Let me try differently."


class TestSessionManagement:
    """Tests for session management."""

    def test_new_session_created(self, orchestrator, mock_llm):
        mock_llm.chat_completion.return_value = LLMResponse(content="Hi")

        assert orchestrator.get_session_count() == 0
        orchestrator.process_message("session-1", "Hello")
        assert orchestrator.get_session_count() == 1

    def test_existing_session_reused(self, orchestrator, mock_llm):
        mock_llm.chat_completion.return_value = LLMResponse(content="Hi")

        orchestrator.process_message("session-1", "Hello")
        orchestrator.process_message("session-1", "How are you?")
        assert orchestrator.get_session_count() == 1

    def test_different_sessions_tracked(self, orchestrator, mock_llm):
        mock_llm.chat_completion.return_value = LLMResponse(content="Hi")

        orchestrator.process_message("session-1", "Hello")
        orchestrator.process_message("session-2", "Hello")
        assert orchestrator.get_session_count() == 2

    def test_clear_session(self, orchestrator, mock_llm):
        mock_llm.chat_completion.return_value = LLMResponse(content="Hi")

        orchestrator.process_message("session-1", "Hello")
        assert orchestrator.clear_session("session-1") is True
        assert orchestrator.get_session_count() == 0

    def test_clear_nonexistent_session(self, orchestrator):
        assert orchestrator.clear_session("nonexistent") is False
